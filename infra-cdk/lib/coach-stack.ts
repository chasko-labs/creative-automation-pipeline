import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as iam from "aws-cdk-lib/aws-iam";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as s3assets from "aws-cdk-lib/aws-s3-assets";
import * as path from "path";

export interface CoachStackProps extends cdk.StackProps {
  projectName: string;
}

// L1 style (matches the reconciled app): zip-asset Node coach lambda +
// public Function URL for the campaign creator's /insights + /ask endpoints.
// Nova Micro only. No VPC, no provisioned concurrency (~$0 idle).
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

    const coachUrl = new lambda.CfnUrl(this, "CoachFunctionUrl", {
      targetFunctionArn: coachLambda.attrArn,
      authType: "NONE",
      cors: {
        allowOrigins: [
          "https://kodiak.bryanchasko.com",
          "https://d37333alc7ojpl.cloudfront.net",
        ],
        allowMethods: ["POST"],
        allowHeaders: ["content-type"],
      },
    });

    new lambda.CfnPermission(this, "CoachFunctionUrlPermission", {
      functionName: coachLambda.ref,
      action: "lambda:InvokeFunctionUrl",
      principal: "*",
      functionUrlAuthType: "NONE",
    });

    this.functionUrl = coachUrl.attrFunctionUrl;
    new cdk.CfnOutput(this, "CoachUrl", {
      value: this.functionUrl,
      description: "Public HTTPS endpoint for campaign coach /insights + /ask",
    });
  }
}
