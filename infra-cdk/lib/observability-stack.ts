import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as iam from "aws-cdk-lib/aws-iam";
import * as logs from "aws-cdk-lib/aws-logs";
import * as xray from "aws-cdk-lib/aws-xray";

export interface ObservabilityStackProps extends cdk.StackProps {
  readonly projectName: string;
}

/**
 * Kodiak creatives observability (adoption base = migrated L1, stack id
 * `kodiak-creatives-observability`). Structured app-log group + kodiak X-Ray
 * sampling rule + a standalone managed policy a future app runtime role
 * attaches for logs + X-Ray writes.
 *
 * R3: the log group gets DeletionPolicy RETAIN. The migrated base defaulted to
 * Delete and live carries none -- RETAIN is the safe intended state so a stack
 * delete never drops operational log history.
 *
 * Tagging: inline tag arrays stripped -- app-level tag set (managed-by=cdk)
 * applies; stack= added per-stack here.
 */
export class ObservabilityStack extends cdk.Stack {
  public readonly creativePipelineLogGroupName: string;
  public readonly kodiakSamplingRuleName: string;
  public readonly observabilityWritePolicyArn: string;

  constructor(scope: Construct, id: string, props: ObservabilityStackProps) {
    super(scope, id, props);

    // structured app logs land here. R3 -- RETAIN.
    const creativePipelineLogGroup = new logs.CfnLogGroup(
      this,
      "CreativePipelineLogGroup",
      {
        logGroupName: "/kodiak/creative-pipeline",
        retentionInDays: 30,
      },
    );
    creativePipelineLogGroup.cfnOptions.deletionPolicy =
      cdk.CfnDeletionPolicy.RETAIN;
    creativePipelineLogGroup.cfnOptions.updateReplacePolicy =
      cdk.CfnDeletionPolicy.RETAIN;

    // X-Ray sampling rule -- captures kodiak traces above the 5% Default rule.
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
    const observabilityWritePolicy = new iam.CfnManagedPolicy(
      this,
      "ObservabilityWritePolicy",
      {
        description:
          "Least-privilege write access for kodiak structured logs + X-Ray traces",
        policyDocument: {
          Version: "2012-10-17",
          Statement: [
            {
              Sid: "WriteStructuredLogs",
              Effect: "Allow",
              Action: [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
              ],
              Resource: [
                creativePipelineLogGroup.attrArn,
                `${creativePipelineLogGroup.attrArn}:*`,
              ],
            },
            {
              Sid: "WriteTracesAndReadSampling",
              Effect: "Allow",
              Action: [
                "xray:PutTraceSegments",
                "xray:PutTelemetryRecords",
                "xray:GetSamplingRules",
                "xray:GetSamplingTargets",
                "xray:GetSamplingStatisticSummaries",
              ],
              Resource: "*",
            },
          ],
        },
      },
    );

    // ---- tags ------------------------------------------------------------
    cdk.Tags.of(this).add("stack", "kodiak-creatives-observability");

    // ---- outputs ---------------------------------------------------------
    this.creativePipelineLogGroupName = creativePipelineLogGroup.ref;
    new cdk.CfnOutput(this, "CreativePipelineLogGroupName", {
      value: this.creativePipelineLogGroupName,
      description: "CloudWatch log group for structured app logs",
    });
    this.kodiakSamplingRuleName = "kodiak-creative";
    new cdk.CfnOutput(this, "KodiakSamplingRuleName", {
      value: this.kodiakSamplingRuleName,
      description: "X-Ray sampling rule name",
    });
    this.observabilityWritePolicyArn = observabilityWritePolicy.ref;
    new cdk.CfnOutput(this, "ObservabilityWritePolicyArn", {
      value: this.observabilityWritePolicyArn,
      description:
        "Managed policy arn a future app runtime role attaches for logs + X-Ray writes",
    });
  }
}
