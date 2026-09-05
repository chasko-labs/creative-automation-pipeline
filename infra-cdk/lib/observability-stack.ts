import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as logs from "aws-cdk-lib/aws-logs";
import * as iam from "aws-cdk-lib/aws-iam";
import * as xray from "aws-cdk-lib/aws-xray";

export interface ObservabilityStackProps extends cdk.StackProps {
  readonly projectName: string;
}

/**
 * Observability primitives for the pipeline: the structured-app-log group, the
 * kodiak X-Ray sampling rule, and a standalone managed policy a future app
 * runtime role attaches for logs + X-Ray writes.
 *
 * This mirrors ../infra/observability.yaml. The log group already exists live;
 * adopt it with `cdk import` if you want CDK to own it (see README), or let the
 * first deploy create it in a fresh environment.
 */
export class ObservabilityStack extends cdk.Stack {
  public readonly appLogGroup: logs.ILogGroup;
  public readonly writePolicy: iam.IManagedPolicy;

  constructor(scope: Construct, id: string, props: ObservabilityStackProps) {
    super(scope, id, props);

    // structured app logs land here. RETAIN -- the group holds operational
    // history a stack delete must not drop.
    const appLogGroup = new logs.LogGroup(this, "CreativePipelineLogGroup", {
      logGroupName: "/kodiak/creative-pipeline",
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });
    this.appLogGroup = appLogGroup;

    // X-Ray sampling rule -- captures kodiak traces above the 5% Default rule.
    // Priority 9000 sits below Default (10000) so it is evaluated first.
    // ServiceName wildcard matches kodiak-creative and any suffixed variant.
    // No L2 construct exists for sampling rules -- CfnSamplingRule is correct.
    new xray.CfnSamplingRule(this, "KodiakSamplingRule", {
      samplingRule: {
        ruleName: "kodiak-creative",
        priority: 9000,
        reservoirSize: 1,
        fixedRate: 0.1,
        serviceName: "kodiak-creative*",
        serviceType: "*",
        host: "*",
        httpMethod: "*",
        urlPath: "*",
        resourceArn: "*",
        version: 1,
      },
    });

    // standalone managed policy for a future app runtime role to attach.
    const writePolicy = new iam.ManagedPolicy(
      this,
      "ObservabilityWritePolicy",
      {
        description:
          "Least-privilege write access for kodiak structured logs + X-Ray traces",
        statements: [
          new iam.PolicyStatement({
            sid: "WriteStructuredLogs",
            effect: iam.Effect.ALLOW,
            actions: [
              "logs:CreateLogGroup",
              "logs:CreateLogStream",
              "logs:PutLogEvents",
            ],
            resources: [
              appLogGroup.logGroupArn,
              `${appLogGroup.logGroupArn}:*`,
            ],
          }),
          // X-Ray write actions do not support resource-level scoping -- AWS
          // requires Resource "*" for Put*. The sampling reads (Get*) are used by
          // the SDK sampler and also only accept "*". Service constraint, not a
          // widening.
          new iam.PolicyStatement({
            sid: "WriteTracesAndReadSampling",
            effect: iam.Effect.ALLOW,
            actions: [
              "xray:PutTraceSegments",
              "xray:PutTelemetryRecords",
              "xray:GetSamplingRules",
              "xray:GetSamplingTargets",
              "xray:GetSamplingStatisticSummaries",
            ],
            resources: ["*"],
          }),
        ],
      },
    );
    this.writePolicy = writePolicy;

    // ---- tags ------------------------------------------------------------
    // project/team/managed-by/repo/environment come from the app-level tag set.
    cdk.Tags.of(this).add("stack", "kodiak-creatives-observability");

    // ---- outputs ---------------------------------------------------------
    new cdk.CfnOutput(this, "CreativePipelineLogGroupName", {
      value: appLogGroup.logGroupName,
      description: "CloudWatch log group for structured app logs",
    });
    new cdk.CfnOutput(this, "KodiakSamplingRuleName", {
      value: "kodiak-creative",
      description: "X-Ray sampling rule name",
    });
    new cdk.CfnOutput(this, "ObservabilityWritePolicyArn", {
      value: writePolicy.managedPolicyArn,
      description:
        "Managed policy arn a future app runtime role attaches for logs + X-Ray writes",
    });
  }
}
