import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as iam from "aws-cdk-lib/aws-iam";
import * as lambda from "aws-cdk-lib/aws-lambda";

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
