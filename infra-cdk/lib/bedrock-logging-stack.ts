import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as logs from "aws-cdk-lib/aws-logs";
import * as iam from "aws-cdk-lib/aws-iam";
import {
  AwsCustomResource,
  AwsCustomResourcePolicy,
  PhysicalResourceId,
} from "aws-cdk-lib/custom-resources";

export interface BedrockLoggingStackProps extends cdk.StackProps {
  readonly projectName: string;
  readonly logGroupName: string;
  /** IAM role name Bedrock assumes. Region-suffixed for the us-west-2 instance. */
  readonly roleName: string;
  /**
   * When true, an AwsCustomResource flips the account+region singleton
   * (PutModelInvocationLoggingConfiguration) to point Bedrock at this stack's
   * log group + role. The exact CLI is also emitted as an output as a fallback.
   */
  readonly enableSingleton: boolean;
}

/**
 * Bedrock model-invocation logging for ONE region.
 *
 * CloudFormation-manageable dependencies: the CloudWatch log group that receives
 * invocation records, and the IAM role Bedrock assumes to write into it.
 *
 * The account-level toggle that points Bedrock at these resources
 * (PutModelInvocationLoggingConfiguration) is NOT a native CloudFormation
 * resource -- it is an account+region SINGLETON. This stack enables it with an
 * AwsCustomResource (a single SDK call at deploy time) and ALSO emits the exact
 * CLI as an output for the operator to run/verify.
 *
 * FIX 2 (cross-region): model-invocation logging is per-region. The original
 * IaC configured only us-east-1, but the custom art-director model runs
 * us-west-2, and the us-east-1-scoped role could not write a us-west-2 log
 * group -- so us-west-2 invocations were never logged. This stack is deployed
 * as TWO instances (us-east-1 + us-west-2, see bin/app.ts). Because the role's
 * write policy is scoped to THIS stack's own (region-local) log group ARN, the
 * us-west-2 instance produces a role correctly scoped to the us-west-2 log
 * group, and the singleton is enabled in us-west-2 too.
 */
export class BedrockLoggingStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: BedrockLoggingStackProps) {
    super(scope, id, props);

    const { logGroupName, roleName, enableSingleton } = props;

    // destination log group Bedrock writes invocation records into. RETAIN --
    // holds production model-invocation history a stack delete must not drop.
    const logGroup = new logs.LogGroup(this, "BedrockLoggingLogGroup", {
      logGroupName,
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // role Bedrock assumes to deliver logs. Trust policy is confused-deputy
    // hardened: SourceAccount pins this account, SourceArn pins the bedrock
    // service arn space in THIS region+account.
    const role = new iam.Role(this, "BedrockLoggingRole", {
      roleName,
      assumedBy: new iam.ServicePrincipal("bedrock.amazonaws.com", {
        conditions: {
          StringEquals: { "aws:SourceAccount": this.account },
          ArnLike: {
            "aws:SourceArn": `arn:aws:bedrock:${this.region}:${this.account}:*`,
          },
        },
      }),
    });

    // least-privilege: only the two write actions Bedrock needs, scoped to the
    // model-invocation stream path inside THIS region's log group. Because
    // logGroup.logGroupArn resolves to the stack's region, the us-west-2
    // instance scopes to the us-west-2 log group ARN -- the core of FIX 2.
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: "WriteBedrockInvocationLogs",
        effect: iam.Effect.ALLOW,
        actions: ["logs:CreateLogStream", "logs:PutLogEvents"],
        resources: [
          logGroup.logGroupArn,
          `${logGroup.logGroupArn}:log-stream:aws/bedrock/modelinvocations`,
        ],
      }),
    );

    // singleton enable via SDK call at deploy time.
    if (enableSingleton) {
      const loggingConfig = {
        cloudWatchConfig: {
          logGroupName,
          roleArn: role.roleArn,
        },
        textDataDeliveryEnabled: true,
        imageDataDeliveryEnabled: true,
        embeddingDataDeliveryEnabled: true,
        videoDataDeliveryEnabled: true,
      };

      const enable = new AwsCustomResource(
        this,
        "EnableModelInvocationLogging",
        {
          // no native resource exists; call the API directly. onUpdate covers
          // create + update. The physical id is region-stable so CDK does not
          // thrash the singleton across deploys.
          onUpdate: {
            service: "Bedrock",
            action: "PutModelInvocationLoggingConfiguration",
            parameters: { loggingConfig },
            physicalResourceId: PhysicalResourceId.of(
              `bedrock-model-invocation-logging-${this.region}`,
            ),
          },
          // deliberately NO onDelete -- the singleton is account-level and may be
          // shared/enabled by hand; a stack delete must not silently disable
          // account-wide model-invocation logging.
          policy: AwsCustomResourcePolicy.fromStatements([
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ["bedrock:PutModelInvocationLoggingConfiguration"],
              resources: ["*"], // account-level setting -- no resource-level ARN
            }),
            // the custom-resource lambda must be able to PassRole the logging role
            // to Bedrock when it sets the configuration.
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ["iam:PassRole"],
              resources: [role.roleArn],
            }),
          ]),
        },
      );
      enable.node.addDependency(role);
      enable.node.addDependency(logGroup);
    }

    // ---- tags ------------------------------------------------------------
    // project/team/managed-by/repo/environment come from the app-level tag set.
    cdk.Tags.of(this).add(
      "stack",
      `kodiak-creatives-bedrock-logging-${this.region}`,
    );

    // ---- outputs ---------------------------------------------------------
    new cdk.CfnOutput(this, "BedrockLoggingLogGroupName", {
      value: logGroup.logGroupName,
      description:
        "CloudWatch log group receiving Bedrock model-invocation logs",
    });
    new cdk.CfnOutput(this, "BedrockLoggingRoleArn", {
      value: role.roleArn,
      description: "IAM role arn Bedrock assumes to write invocation logs",
    });
    // fallback / verify CLI -- identical shape to the old EnableLoggingCommand
    // output, region substituted from the stack env.
    new cdk.CfnOutput(this, "EnableLoggingCommand", {
      description:
        "Post-deploy CLI to (re)enable / verify the account+region singleton for this region",
      value: [
        "aws bedrock put-model-invocation-logging-configuration",
        `--region ${this.region}`,
        `--logging-config '{"cloudWatchConfig":{"logGroupName":"${logGroupName}","roleArn":"${role.roleArn}"},"textDataDeliveryEnabled":true,"imageDataDeliveryEnabled":true,"embeddingDataDeliveryEnabled":true,"videoDataDeliveryEnabled":true}'`,
      ].join(" "),
    });
  }
}
