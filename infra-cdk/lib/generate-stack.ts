import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as iam from "aws-cdk-lib/aws-iam";
import * as lambda from "aws-cdk-lib/aws-lambda";
import {
  KODIAK_VECTOR_BUCKET_NAME,
  KODIAK_VECTOR_INDEX_NAME,
  KODIAK_VECTOR_BUCKET_ARN,
  KODIAK_VECTOR_INDEX_ARN,
  BEDROCK_EMBED_MODEL_ARN,
  BEDROCK_EMBED_FALLBACK_MODEL_ARN,
  DAM_LIBRARY_PREFIX,
} from "./config";

export interface GenerateStackProps extends cdk.StackProps {
  readonly projectName: string;
  readonly damBucketName: string;
  /**
   * ECR image uri for the generation Lambda container. The image is built +
   * pushed to ECR BEFORE deploy (see README); this stack only references it.
   * Falls back to context key `generateImageUri`, then to the live
   * :latest tag in the account ECR repo.
   */
  readonly imageUri?: string;
}

/**
 * Kodiak creatives generate endpoint (adoption base = migrated L1, stack id
 * `kodiak-creatives-generate`). Container-image Lambda that runs Bedrock
 * (Nova Pro art-direction + Stability control-structure / outpaint) plus
 * Pillow, writes the rendered PNG to the DAM bucket under
 * brands/kodiak/renders/, and is fronted by a public (dev-open) Function URL.
 *
 * FIX 1 (R2, intentional live-behavior change on next deploy): X-Ray Tracing
 * ACTIVE on the function + env AWS_XRAY_SDK_ENABLED=true + the
 * xray:PutTraceSegments / PutTelemetryRecords statement on the role. The
 * migrated base was pre-fix (Mode absent, flag "false", no xray statement);
 * all three are added here so the run-ledger trace_id is populated.
 *
 * Tagging: inline managed-by=cloudformation tag arrays stripped -- app-level
 * tag set (managed-by=cdk) applies; stack= added per-stack here.
 */
export class GenerateStack extends cdk.Stack {
  public readonly functionUrl: string;
  public readonly lambdaName: string;
  public readonly lambdaRoleArn: string;

  constructor(scope: Construct, id: string, props: GenerateStackProps) {
    super(scope, id, props);

    const { damBucketName } = props;

    const imageUri =
      props.imageUri ??
      (this.node.tryGetContext("generateImageUri") as string | undefined) ??
      `${this.account}.dkr.ecr.${this.region}.amazonaws.com/kodiak-creatives-generate:latest`;

    // ---- execution role --------------------------------------------------
    const generateLambdaRole = new iam.CfnRole(this, "GenerateLambdaRole", {
      assumeRolePolicyDocument: {
        Version: "2012-10-17",
        Statement: [
          {
            Effect: "Allow",
            Principal: { Service: "lambda.amazonaws.com" },
            Action: "sts:AssumeRole",
          },
        ],
      },
      managedPolicyArns: [
        "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
      ],
      policies: [
        {
          policyName: "generate-lambda-inline",
          policyDocument: {
            Version: "2012-10-17",
            Statement: [
              {
                Sid: "BedrockInvokeNovaPro",
                Effect: "Allow",
                Action: "bedrock:InvokeModel",
                Resource:
                  "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-pro-v1:0",
              },
              {
                Sid: "BedrockInvokeArtDirector",
                Effect: "Allow",
                // Art-director voice model -- custom imported model in us-west-2 (isolated
                // from the us-east-1 pipeline on purpose; art_director.py carries
                // KODIAK_ARTDIRECTOR_REGION and never falls back to AWS_REGION). Gated dark
                // at runtime behind KODIAK_ARTDIRECTOR_ENABLED.
                Action: "bedrock:InvokeModel",
                Resource:
                  "arn:aws:bedrock:us-west-2:946179428633:imported-model/cx15b77k5nge",
              },
              {
                Sid: "BedrockInvokeStabilityControlStructure",
                Effect: "Allow",
                Action: "bedrock:InvokeModel",
                Resource: [
                  "arn:aws:bedrock:us-east-1:946179428633:inference-profile/us.stability.stable-image-control-structure-v1:0",
                  "arn:aws:bedrock:us-east-1::foundation-model/stability.stable-image-control-structure-v1:0",
                  "arn:aws:bedrock:us-east-2::foundation-model/stability.stable-image-control-structure-v1:0",
                  "arn:aws:bedrock:us-west-2::foundation-model/stability.stable-image-control-structure-v1:0",
                ],
              },
              {
                Sid: "BedrockInvokeStabilityOutpaint",
                Effect: "Allow",
                Action: "bedrock:InvokeModel",
                Resource: [
                  "arn:aws:bedrock:us-east-1:946179428633:inference-profile/us.stability.stable-outpaint-v1:0",
                  "arn:aws:bedrock:us-east-1::foundation-model/stability.stable-outpaint-v1:0",
                  "arn:aws:bedrock:us-east-2::foundation-model/stability.stable-outpaint-v1:0",
                  "arn:aws:bedrock:us-west-2::foundation-model/stability.stable-outpaint-v1:0",
                ],
              },
              {
                Sid: "DamRendersReadWrite",
                Effect: "Allow",
                Action: ["s3:PutObject", "s3:GetObject"],
                Resource: `arn:aws:s3:::${damBucketName}/brands/kodiak/renders/*`,
              },
              // User-upload library prefix. asset_library.py writes uploads to
              // brands/kodiak/library/* -- the DamRendersReadWrite statement
              // above only covers renders/*, so the library prefix needs its
              // own scoped grant (not a widening of the renders statement).
              {
                Sid: "DamLibraryReadWrite",
                Effect: "Allow",
                Action: ["s3:PutObject", "s3:GetObject"],
                Resource: `arn:aws:s3:::${damBucketName}/${DAM_LIBRARY_PREFIX}*`,
              },
              // S3 Vectors read/write on the Kodiak vector bucket + index only.
              // Scoped to the specific bucket ARN and its index sub-resource --
              // no wildcards. The bucket-level ARN covers ListVectors; the
              // index ARN covers Put/Get/Query on the vectors themselves.
              {
                Sid: "KodiakS3VectorsReadWrite",
                Effect: "Allow",
                Action: [
                  "s3vectors:PutVectors",
                  "s3vectors:GetVectors",
                  "s3vectors:QueryVectors",
                  "s3vectors:ListVectors",
                ],
                Resource: [KODIAK_VECTOR_BUCKET_ARN, KODIAK_VECTOR_INDEX_ARN],
              },
              // Bedrock embedding models: Nova multimodal (primary) + Titan
              // text-only (fallback in embeddings.py). Two named model ARNs in
              // one statement -- no wildcards.
              {
                Sid: "BedrockInvokeEmbedModels",
                Effect: "Allow",
                Action: "bedrock:InvokeModel",
                Resource: [
                  BEDROCK_EMBED_MODEL_ARN,
                  BEDROCK_EMBED_FALLBACK_MODEL_ARN,
                ],
              },
              // FIX 1 -- X-Ray write actions. ACTIVE tracing (set on the
              // function below) needs the role to ship segments.
              // xray:Put* does not support resource-level scoping -- AWS
              // requires Resource "*". Service constraint, not a widening.
              {
                Sid: "WriteXRayTraces",
                Effect: "Allow",
                Action: ["xray:PutTraceSegments", "xray:PutTelemetryRecords"],
                Resource: "*",
              },
            ],
          },
        },
      ],
    });

    // ---- function --------------------------------------------------------
    const generateLambda = new lambda.CfnFunction(this, "GenerateLambda", {
      packageType: "Image",
      code: { imageUri },
      role: generateLambdaRole.attrArn,
      // 300s accommodates 4 serial Bedrock GenAI round-trips. 60s killed it.
      timeout: 300,
      // 3008 MB buys proportional vCPU for Pillow compositing + boto3 TLS.
      memorySize: 3008,
      // FIX 1 -- ACTIVE makes the lambda sample + emit its own X-Ray segments
      // so the run-ledger trace_id is populated (was PassThrough / absent).
      tracingConfig: { mode: "Active" },
      environment: {
        variables: {
          DAM_S3_BUCKET: damBucketName,
          // FIX 1 -- was "false". Enables aws-xray-sdk inside the handler so
          // downstream boto3 (Bedrock, S3) calls are captured as subsegments.
          AWS_XRAY_SDK_ENABLED: "true",
          // S3 Vectors target for the ingest/embedding path. The runtime reads
          // these to write + query vectors. BEDROCK_EMBED_MODEL / BEDROCK_EMBED_DIM
          // default in embeddings.py (Nova multimodal / 1024) and are not
          // overridden here.
          KODIAK_VECTOR_BUCKET: KODIAK_VECTOR_BUCKET_NAME,
          KODIAK_VECTOR_INDEX: KODIAK_VECTOR_INDEX_NAME,
        },
      },
    });

    // public, dev-open Function URL. The site calls it directly, unsigned.
    const generateFunctionUrl = new lambda.CfnUrl(this, "GenerateFunctionUrl", {
      targetFunctionArn: generateLambda.attrArn,
      authType: "NONE",
      cors: {
        allowOrigins: ["*"],
        allowMethods: ["POST"],
        allowHeaders: ["content-type"],
      },
    });

    new lambda.CfnPermission(this, "GenerateFunctionUrlPermission", {
      functionName: generateLambda.ref,
      action: "lambda:InvokeFunctionUrl",
      principal: "*",
      functionUrlAuthType: "NONE",
    });

    // ---- tags ------------------------------------------------------------
    cdk.Tags.of(this).add("stack", "kodiak-creatives-generate");

    // ---- outputs ---------------------------------------------------------
    this.functionUrl = generateFunctionUrl.attrFunctionUrl;
    new cdk.CfnOutput(this, "FunctionUrl", {
      value: this.functionUrl,
      description: "Public HTTPS endpoint for prompt-to-image generation",
    });
    this.lambdaName = generateLambda.ref;
    new cdk.CfnOutput(this, "LambdaName", {
      value: this.lambdaName,
      description: "Name of the generation Lambda function",
    });
    this.lambdaRoleArn = generateLambdaRole.attrArn;
    new cdk.CfnOutput(this, "LambdaRoleArn", {
      value: this.lambdaRoleArn,
      description: "ARN of the Lambda execution role",
    });
  }
}
