import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as iam from "aws-cdk-lib/aws-iam";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as apigwv2 from "aws-cdk-lib/aws-apigatewayv2";
import * as s3assets from "aws-cdk-lib/aws-s3-assets";
import * as path from "path";

export interface CoachStackProps extends cdk.StackProps {
  projectName: string;
}

// L1 style (matches the reconciled app): zip-asset Node coach lambda +
// public HTTP API fronting /insights + /ask for the campaign creator.
// Nova Micro only. No VPC, no provisioned concurrency (~$0 idle).
// NOTE: first cut used a Lambda Function URL (auth NONE + InvokeFunctionUrl
// permission, byte-verified) but the URL plane denied every caller — anonymous
// AND SigV4-signed — with AccessDeniedException while direct IAM invoke worked
// and CORS preflight returned 200. API Gateway HTTP API verified end-to-end
// instead; single public surface, throttling available if abused.
export class CoachStack extends cdk.Stack {
  public readonly functionUrl: string;

  constructor(scope: Construct, id: string, props: CoachStackProps) {
    super(scope, id, props);

    const asset = new s3assets.Asset(this, "CoachCode", {
      path: path.join(__dirname, "..", "..", "coach"),
      exclude: ["node_modules", "*.log"],
    });

    const coachRole = new iam.CfnRole(this, "CoachLambdaRole", {
      assumeRolePolicyDocument: {
        Version: "2012-10-17",
        Statement: [{
          Effect: "Allow",
          Principal: { Service: "lambda.amazonaws.com" },
          Action: "sts:AssumeRole",
        }],
      },
      managedPolicyArns: [
        `arn:${this.partition}:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole`,
      ],
      policies: [{
        policyName: "BedrockInvokeNovaMicro",
        policyDocument: {
          Version: "2012-10-17",
          Statement: [{
            Effect: "Allow",
            Action: "bedrock:InvokeModel",
            Resource: `arn:${this.partition}:bedrock:${this.region}::foundation-model/amazon.nova-micro-v1:0`,
          }],
        },
      }],
    });

    const coachLambda = new lambda.CfnFunction(this, "CoachLambda", {
      runtime: "nodejs22.x",
      handler: "index.handler",
      code: { s3Bucket: asset.s3BucketName, s3Key: asset.s3ObjectKey },
      role: coachRole.attrArn,
      timeout: 30,
      memorySize: 256,
      environment: {
        variables: { MODEL_ID: "amazon.nova-micro-v1:0" },
      },
    });
    coachLambda.addDependency(coachRole);

    // HTTP API (pay-per-request, ~$0 idle): single greedy POST route; the handler
    // already speaks proxy v2.0 events (version/routeKey/rawPath), unchanged.
    const api = new apigwv2.CfnApi(this, "CoachApi", {
      name: "kodiak-coach",
      protocolType: "HTTP",
      corsConfiguration: {
        allowOrigins: [
          "https://kodiak.bryanchasko.com",
          "https://d37333alc7ojpl.cloudfront.net",
        ],
        allowMethods: ["POST"],
        allowHeaders: ["content-type"],
      },
    });
    const integration = new apigwv2.CfnIntegration(this, "CoachIntegration", {
      apiId: api.ref,
      integrationType: "AWS_PROXY",
      integrationUri: coachLambda.attrArn,
      payloadFormatVersion: "2.0",
    });
    new apigwv2.CfnRoute(this, "CoachPostRoute", {
      apiId: api.ref,
      routeKey: "POST /{proxy+}",
      target: `integrations/${integration.ref}`,
    });
    new apigwv2.CfnStage(this, "CoachDefaultStage", {
      apiId: api.ref,
      stageName: "$default",
      autoDeploy: true,
    });
    new lambda.CfnPermission(this, "CoachApiInvokePermission", {
      functionName: coachLambda.ref,
      action: "lambda:InvokeFunction",
      principal: "apigateway.amazonaws.com",
      sourceArn: `arn:${this.partition}:execute-api:${this.region}:${this.account}:${api.ref}/*/*`,
    });

    this.functionUrl =
      `https://${api.ref}.execute-api.${this.region}.amazonaws.com/`;
    new cdk.CfnOutput(this, "CoachUrl", {
      value: this.functionUrl,
      description: "Public HTTPS endpoint for campaign coach /insights + /ask",
    });
  }
}
