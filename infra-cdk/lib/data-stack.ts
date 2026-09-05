import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as codebuild from "aws-cdk-lib/aws-codebuild";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as iam from "aws-cdk-lib/aws-iam";
import * as s3 from "aws-cdk-lib/aws-s3";

export interface DataStackProps extends cdk.StackProps {
  readonly projectName: string;
  /**
   * Live DAM bucket name (globally unique). Defaults to the live us-east-1
   * bucket. Change only for a second/throwaway environment.
   */
  readonly damBucketName: string;
}

/**
 * Kodiak creatives main stack (adoption base = migrated L1, stack id
 * `kodiak-creatives`). Superset of the retired hand-authored DataStack: it adds
 * the CreativePipelineLogBucket, the per-push CodeBuild CI project + its
 * service role, and the explicit TLS-only bucket policy that #122 never
 * modeled -- alongside the DAM bucket + localization-memory / retail-network
 * tables.
 *
 * Every stateful resource carries DeletionPolicy RETAIN so a stack delete never
 * drops live data. Generated verbatim from the live template by `cdk migrate`
 * (migrate.json Source = kodiak-creatives), so the L1 Cfn* constructs mirror
 * the live resources byte-for-byte and adopt with zero drift.
 *
 * Tagging: the repeated inline `managed-by=cloudformation` tag arrays the
 * migrated template carried are stripped -- the uniform app-level tag set
 * (managed-by=cdk) is applied in bin/app.ts. brand=kodiak is scoped to the DAM
 * bucket only; stack= is applied per-stack here.
 */
export class DataStack extends cdk.Stack {
  public readonly styleLibraryBucketName: string;
  public readonly localizationMemoryTableName: string;
  public readonly retailNetworkTableName: string;
  public readonly logBucketName: string;
  public readonly codeBuildProjectName: string;
  public readonly codeBuildServiceRoleArn: string;

  constructor(scope: Construct, id: string, props: DataStackProps) {
    super(scope, id, props);

    const { projectName, damBucketName } = props;

    // ---- CodeBuild CI service role (CloudWatch Logs only) ----------------
    const codeBuildServiceRole = new iam.CfnRole(this, "CodeBuildServiceRole", {
      roleName: `${projectName}-ci-role`,
      assumeRolePolicyDocument: {
        Version: "2012-10-17",
        Statement: [
          {
            Effect: "Allow",
            Principal: { Service: "codebuild.amazonaws.com" },
            Action: "sts:AssumeRole",
          },
        ],
      },
      policies: [
        {
          policyName: "cloudwatch-logs",
          policyDocument: {
            Version: "2012-10-17",
            Statement: [
              {
                Sid: "WriteOwnLogGroup",
                Effect: "Allow",
                Action: [
                  "logs:CreateLogGroup",
                  "logs:CreateLogStream",
                  "logs:PutLogEvents",
                ],
                Resource: [
                  `arn:${this.partition}:logs:${this.region}:${this.account}:log-group:/codebuild/${projectName}-ci`,
                  `arn:${this.partition}:logs:${this.region}:${this.account}:log-group:/codebuild/${projectName}-ci:*`,
                ],
              },
            ],
          },
        },
      ],
    });

    // ---- CI/CD access-log bucket (versioned, KMS, RETAIN) ----------------
    const creativePipelineLogBucket = new s3.CfnBucket(
      this,
      "CreativePipelineLogBucket",
      {
        bucketName: `${projectName}-logs-${this.account}-${this.region}`,
        versioningConfiguration: { status: "Enabled" },
        publicAccessBlockConfiguration: {
          blockPublicAcls: true,
          blockPublicPolicy: true,
          ignorePublicAcls: true,
          restrictPublicBuckets: true,
        },
        bucketEncryption: {
          serverSideEncryptionConfiguration: [
            {
              serverSideEncryptionByDefault: { sseAlgorithm: "aws:kms" },
              bucketKeyEnabled: true,
            },
          ],
        },
      },
    );
    creativePipelineLogBucket.cfnOptions.deletionPolicy =
      cdk.CfnDeletionPolicy.RETAIN;
    creativePipelineLogBucket.cfnOptions.updateReplacePolicy =
      cdk.CfnDeletionPolicy.RETAIN;

    // ---- DynamoDB: localization memory (PITR, RETAIN) --------------------
    const localizationMemoryTable = new dynamodb.CfnTable(
      this,
      "LocalizationMemoryTable",
      {
        tableName: `${projectName}-localization-memory`,
        billingMode: "PAY_PER_REQUEST",
        attributeDefinitions: [
          { attributeName: "market", attributeType: "S" },
          { attributeName: "place_message_id", attributeType: "S" },
        ],
        keySchema: [
          { attributeName: "market", keyType: "HASH" },
          { attributeName: "place_message_id", keyType: "RANGE" },
        ],
        pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      },
    );
    localizationMemoryTable.cfnOptions.deletionPolicy =
      cdk.CfnDeletionPolicy.RETAIN;
    localizationMemoryTable.cfnOptions.updateReplacePolicy =
      cdk.CfnDeletionPolicy.RETAIN;

    // ---- DynamoDB: retail network (GSI byMarket, RETAIN) -----------------
    const retailNetworkTable = new dynamodb.CfnTable(
      this,
      "RetailNetworkTable",
      {
        tableName: `${projectName}-retail-network`,
        billingMode: "PAY_PER_REQUEST",
        attributeDefinitions: [
          { attributeName: "store_id", attributeType: "S" },
          { attributeName: "market", attributeType: "S" },
        ],
        keySchema: [{ attributeName: "store_id", keyType: "HASH" }],
        globalSecondaryIndexes: [
          {
            indexName: "byMarket",
            keySchema: [{ attributeName: "market", keyType: "HASH" }],
            projection: { projectionType: "ALL" },
          },
        ],
      },
    );
    retailNetworkTable.cfnOptions.deletionPolicy = cdk.CfnDeletionPolicy.RETAIN;
    retailNetworkTable.cfnOptions.updateReplacePolicy =
      cdk.CfnDeletionPolicy.RETAIN;

    // ---- DAM (style library) bucket -- LIVE DATA, RETAIN -----------------
    // versioned + aws:kms SSE + bucket-key + full public-access block +
    // lifecycle (abort MPU 7d + renders tiering). Mirrors the live bucket so
    // `cdk import` adopts it with zero drift.
    const styleLibraryBucket = new s3.CfnBucket(this, "StyleLibraryBucket", {
      bucketName: damBucketName,
      versioningConfiguration: { status: "Enabled" },
      publicAccessBlockConfiguration: {
        blockPublicAcls: true,
        blockPublicPolicy: true,
        ignorePublicAcls: true,
        restrictPublicBuckets: true,
      },
      bucketEncryption: {
        serverSideEncryptionConfiguration: [
          {
            serverSideEncryptionByDefault: { sseAlgorithm: "aws:kms" },
            bucketKeyEnabled: true,
          },
        ],
      },
      lifecycleConfiguration: {
        rules: [
          {
            id: "abort-multipart",
            status: "Enabled",
            prefix: "",
            abortIncompleteMultipartUpload: { daysAfterInitiation: 7 },
          },
          {
            id: "renders-archive",
            status: "Enabled",
            prefix: "brands/kodiak/renders/",
            transitions: [
              { storageClass: "STANDARD_IA", transitionInDays: 90 },
              { storageClass: "GLACIER", transitionInDays: 180 },
              { storageClass: "DEEP_ARCHIVE", transitionInDays: 365 },
            ],
            noncurrentVersionTransitions: [
              {
                storageClass: "STANDARD_IA",
                transitionInDays: 30,
                newerNoncurrentVersions: 2,
              },
            ],
          },
        ],
      },
    });
    styleLibraryBucket.cfnOptions.deletionPolicy = cdk.CfnDeletionPolicy.RETAIN;
    styleLibraryBucket.cfnOptions.updateReplacePolicy =
      cdk.CfnDeletionPolicy.RETAIN;

    // brand=kodiak is SCOPED to the DAM bucket only (not app-wide).
    cdk.Tags.of(styleLibraryBucket).add("brand", "kodiak");

    // ---- per-push CI gate ------------------------------------------------
    const creativePipelineCi = new codebuild.CfnProject(
      this,
      "CreativePipelineCI",
      {
        name: `${projectName}-ci`,
        description: `Fast per-push CI gate for ${projectName} - ruff, pytest, cfn-lint`,
        serviceRole: codeBuildServiceRole.attrArn,
        timeoutInMinutes: 20,
        source: {
          type: "GITHUB",
          location:
            "https://github.com/chasko-labs/creative-automation-pipeline.git",
          buildSpec: "buildspec.yml",
          reportBuildStatus: true,
          gitCloneDepth: 1,
        },
        artifacts: { type: "NO_ARTIFACTS" },
        environment: {
          type: "LINUX_CONTAINER",
          computeType: "BUILD_GENERAL1_SMALL",
          image: "aws/codebuild/amazonlinux2-x86_64-standard:5.0",
          environmentVariables: [
            { name: "RUN_SLOW", value: "false", type: "PLAINTEXT" },
          ],
        },
        triggers: {
          webhook: true,
          filterGroups: [
            [{ type: "EVENT", pattern: "PUSH" }],
            [
              {
                type: "EVENT",
                pattern:
                  "PULL_REQUEST_CREATED,PULL_REQUEST_UPDATED,PULL_REQUEST_REOPENED",
              },
            ],
          ],
        },
        logsConfig: {
          cloudWatchLogs: {
            status: "ENABLED",
            groupName: `/codebuild/${projectName}-ci`,
          },
        },
      },
    );

    // ---- TLS-only DAM bucket policy (RETAIN) -----------------------------
    const styleLibraryBucketPolicyTlsOnly = new s3.CfnBucketPolicy(
      this,
      "StyleLibraryBucketPolicyTLSOnly",
      {
        bucket: styleLibraryBucket.ref,
        policyDocument: {
          Version: "2012-10-17",
          Statement: [
            {
              Sid: "DenyInsecureTransport",
              Effect: "Deny",
              Principal: "*",
              Action: "s3:*",
              Resource: [
                `${styleLibraryBucket.attrArn}`,
                `${styleLibraryBucket.attrArn}/*`,
              ],
              Condition: { Bool: { "aws:SecureTransport": false } },
            },
          ],
        },
      },
    );
    styleLibraryBucketPolicyTlsOnly.cfnOptions.deletionPolicy =
      cdk.CfnDeletionPolicy.RETAIN;
    styleLibraryBucketPolicyTlsOnly.cfnOptions.updateReplacePolicy =
      cdk.CfnDeletionPolicy.RETAIN;

    // ---- tags ------------------------------------------------------------
    // project/team/managed-by/repo/environment come from the app-level tag set.
    cdk.Tags.of(this).add("stack", "kodiak-creatives");

    // ---- outputs ---------------------------------------------------------
    this.styleLibraryBucketName = styleLibraryBucket.ref;
    new cdk.CfnOutput(this, "StyleLibraryBucketName", {
      value: this.styleLibraryBucketName,
      description:
        "Cloud storage bucket - use as DAM_S3_BUCKET with prefix brands/kodiak/",
    });
    new cdk.CfnOutput(this, "StyleLibraryPrefix", { value: "brands/kodiak/" });
    this.localizationMemoryTableName = localizationMemoryTable.ref;
    new cdk.CfnOutput(this, "LocalizationMemoryTableName", {
      value: this.localizationMemoryTableName,
    });
    this.retailNetworkTableName = retailNetworkTable.ref;
    new cdk.CfnOutput(this, "RetailNetworkTableName", {
      value: this.retailNetworkTableName,
    });
    this.logBucketName = creativePipelineLogBucket.ref;
    new cdk.CfnOutput(this, "LogBucketName", { value: this.logBucketName });
    this.codeBuildProjectName = creativePipelineCi.ref;
    new cdk.CfnOutput(this, "CodeBuildProjectName", {
      value: this.codeBuildProjectName,
      description: "Per-push CI gate project name",
    });
    this.codeBuildServiceRoleArn = codeBuildServiceRole.attrArn;
    new cdk.CfnOutput(this, "CodeBuildServiceRoleArn", {
      value: this.codeBuildServiceRoleArn,
      description: "Least-privilege CodeBuild service role arn (CloudWatch Logs only)",
    });
  }
}
