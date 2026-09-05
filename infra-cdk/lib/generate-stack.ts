import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as ecr from "aws-cdk-lib/aws-ecr";
import * as iam from "aws-cdk-lib/aws-iam";

export interface GenerateStackProps extends cdk.StackProps {
  readonly projectName: string;
  readonly damBucketName: string;
  /** ECR repo the generate container image is pushed to. Default kodiak-creatives-generate. */
  readonly ecrRepositoryName?: string;
  /** image tag to deploy. Default latest. Override via -c generateImageTag=... */
  readonly imageTag?: string;
}

/**
 * Prompt-to-image generation endpoint.
 *
 * Container-image Lambda (PackageType Image) that runs Bedrock (Nova Pro
 * art-direction + Stability control-structure/outpaint) plus Pillow, writes the
 * rendered PNG to the DAM bucket under brands/kodiak/renders/, and is fronted by
 * a public (dev-open) Lambda Function URL.
 *
 * The image is built + pushed to ECR BEFORE deploy (see README). This stack
 * references it by repo name + tag; it does not build the image.
 */
export class GenerateStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: GenerateStackProps) {
    super(scope, id, props);

    const { damBucketName } = props;
    const repoName =
      props.ecrRepositoryName ??
      (this.node.tryGetContext("generateEcrRepo") as string | undefined) ??
      "kodiak-creatives-generate";
    const imageTag =
      props.imageTag ??
      (this.node.tryGetContext("generateImageTag") as string | undefined) ??
      "latest";

    // reference the pre-built image in an existing ECR repo (built + pushed out
    // of band -- CloudFormation only references it, mirroring the old
    // ImageUri parameter).
    const repo = ecr.Repository.fromRepositoryName(
      this,
      "GenerateImageRepo",
      repoName,
    );

    // ---- execution role --------------------------------------------------
    const role = new iam.Role(this, "GenerateLambdaRole", {
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AWSLambdaBasicExecutionRole",
        ),
      ],
    });

    // Nova Pro (Converse) art-directs the scene prompt + caption.
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: "BedrockInvokeNovaPro",
        effect: iam.Effect.ALLOW,
        actions: ["bedrock:InvokeModel"],
        resources: [
          "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-pro-v1:0",
        ],
      }),
    );

    // Stability control-structure. The us.* inference profile authorizes against
    // BOTH the profile ARN AND every foundation-model ARN it routes to
    // (us-east-1/-2, us-west-2) -- all listed.
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: "BedrockInvokeStabilityControlStructure",
        effect: iam.Effect.ALLOW,
        actions: ["bedrock:InvokeModel"],
        resources: [
          `arn:aws:bedrock:us-east-1:${this.account}:inference-profile/us.stability.stable-image-control-structure-v1:0`,
          "arn:aws:bedrock:us-east-1::foundation-model/stability.stable-image-control-structure-v1:0",
          "arn:aws:bedrock:us-east-2::foundation-model/stability.stable-image-control-structure-v1:0",
          "arn:aws:bedrock:us-west-2::foundation-model/stability.stable-image-control-structure-v1:0",
        ],
      }),
    );

    // Stability outpaint. Same inference-profile + foundation-model dual grant.
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: "BedrockInvokeStabilityOutpaint",
        effect: iam.Effect.ALLOW,
        actions: ["bedrock:InvokeModel"],
        resources: [
          `arn:aws:bedrock:us-east-1:${this.account}:inference-profile/us.stability.stable-outpaint-v1:0`,
          "arn:aws:bedrock:us-east-1::foundation-model/stability.stable-outpaint-v1:0",
          "arn:aws:bedrock:us-east-2::foundation-model/stability.stable-outpaint-v1:0",
          "arn:aws:bedrock:us-west-2::foundation-model/stability.stable-outpaint-v1:0",
        ],
      }),
    );

    // DAM renders read/write -- scoped to the renders prefix only.
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: "DamRendersReadWrite",
        effect: iam.Effect.ALLOW,
        actions: ["s3:PutObject", "s3:GetObject"],
        resources: [`arn:aws:s3:::${damBucketName}/brands/kodiak/renders/*`],
      }),
    );

    // FIX 1 -- X-Ray write actions for the generate lambda. Active tracing (set
    // below) needs the role to be able to ship segments. xray:Put* actions do
    // not support resource-level scoping -- AWS requires Resource "*" for
    // PutTraceSegments / PutTelemetryRecords. This is a service constraint, not
    // a widening. WHY active tracing: the run-ledger correlates each generate
    // invocation to a trace_id, which is only populated when the segment is
    // emitted to X-Ray. PassThrough left trace_id blank in the ledger.
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: "WriteXRayTraces",
        effect: iam.Effect.ALLOW,
        actions: ["xray:PutTraceSegments", "xray:PutTelemetryRecords"],
        resources: ["*"],
      }),
    );

    // ---- function --------------------------------------------------------
    const fn = new lambda.DockerImageFunction(this, "GenerateLambda", {
      code: lambda.DockerImageCode.fromEcr(repo, { tagOrDigest: imageTag }),
      role,
      // 300s accommodates 4 serial Bedrock GenAI round-trips (Nova Pro scene +
      // Stability control-structure + 2x outpaint). 60s killed it mid-outpaint.
      timeout: cdk.Duration.seconds(300),
      // 3008 MB buys proportional vCPU for Pillow compositing + boto3 TLS around
      // each Bedrock call. Image work, not memory-bound -- do not go higher.
      memorySize: 3008,
      // FIX 1 -- was Mode=PassThrough. ACTIVE makes the lambda sample + emit its
      // own X-Ray segments so run-ledger trace_id is populated.
      tracing: lambda.Tracing.ACTIVE,
      environment: {
        DAM_S3_BUCKET: damBucketName,
        // FIX 1 -- was "false". Enables the aws-xray-sdk inside the handler so
        // downstream boto3 (Bedrock, S3) calls are captured as subsegments.
        AWS_XRAY_SDK_ENABLED: "true",
      },
    });

    // public, dev-open Function URL. The site calls it directly, unsigned.
    // Tighten to AWS_IAM before any production/public exposure.
    const fnUrl = fn.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.NONE,
      cors: {
        allowedOrigins: ["*"],
        // Function URLs answer the CORS preflight (OPTIONS) automatically, so
        // only the real invocation method (POST) is listed.
        allowedMethods: [lambda.HttpMethod.POST],
        allowedHeaders: ["content-type"],
      },
    });

    // ---- tags ------------------------------------------------------------
    // project/team/managed-by/repo/environment come from the app-level tag set.
    cdk.Tags.of(this).add("stack", "kodiak-creatives-generate");

    // ---- outputs ---------------------------------------------------------
    new cdk.CfnOutput(this, "FunctionUrl", {
      value: fnUrl.url,
      description: "Public HTTPS endpoint for prompt-to-image generation",
    });
    new cdk.CfnOutput(this, "LambdaName", { value: fn.functionName });
    new cdk.CfnOutput(this, "LambdaRoleArn", { value: role.roleArn });
  }
}
