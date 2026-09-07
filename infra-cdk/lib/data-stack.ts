import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as s3vectors from "aws-cdk-lib/aws-s3vectors";
import {
  KODIAK_VECTOR_BUCKET_NAME,
  KODIAK_VECTOR_INDEX_NAME,
  KODIAK_VECTOR_DIMENSION,
  KODIAK_VECTOR_DISTANCE_METRIC,
  KODIAK_VECTOR_DATA_TYPE,
} from "./config";

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
 * the CreativePipelineLogBucket and the explicit TLS-only bucket policy that
 * #122 never modeled -- alongside the DAM bucket + localization-memory /
 * retail-network tables.
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
  public readonly vectorBucketName: string;
  public readonly vectorIndexName: string;
  public readonly vectorBucketArn: string;
  public readonly vectorIndexArn: string;

  constructor(scope: Construct, id: string, props: DataStackProps) {
    super(scope, id, props);

    const { projectName, damBucketName } = props;

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
        // single-table pk/sk keys -- pk=MARKET#<market>, sk=LANG#<lang>#MSG#<sha1-16>; matches localize_memory.build_key. The flat market/place_message_id schema had zero code consumers.
        attributeDefinitions: [
          { attributeName: "pk", attributeType: "S" },
          { attributeName: "sk", attributeType: "S" },
        ],
        keySchema: [
          { attributeName: "pk", keyType: "HASH" },
          { attributeName: "sk", keyType: "RANGE" },
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

    // ---- S3 Vectors: first Kodiak vector store (RETAIN) ------------------
    // Dedicated Amazon S3 Vectors vector bucket + index for the Nova
    // multimodal embeddings (1024 dims, cosine, float32). Authored as CDK L1
    // (aws-s3vectors CfnVectorBucket / CfnIndex) so it is IaC-managed from
    // creation -- closes the drift gap that a hand-created bucket would open.
    // Stateful, so RETAIN on delete (a stack delete never drops vectors; note
    // S3 Vectors only deletes EMPTY buckets, so RETAIN is the safe default).
    const kodiakVectorBucket = new s3vectors.CfnVectorBucket(
      this,
      "KodiakVectorBucket",
      {
        vectorBucketName: KODIAK_VECTOR_BUCKET_NAME,
        // Default SSE-S3 (AES256) -- no customer-managed KMS key required.
      },
    );
    kodiakVectorBucket.cfnOptions.deletionPolicy = cdk.CfnDeletionPolicy.RETAIN;
    kodiakVectorBucket.cfnOptions.updateReplacePolicy =
      cdk.CfnDeletionPolicy.RETAIN;

    const kodiakVectorIndex = new s3vectors.CfnIndex(this, "KodiakVectorIndex", {
      vectorBucketName: KODIAK_VECTOR_BUCKET_NAME,
      indexName: KODIAK_VECTOR_INDEX_NAME,
      dataType: KODIAK_VECTOR_DATA_TYPE,
      dimension: KODIAK_VECTOR_DIMENSION,
      distanceMetric: KODIAK_VECTOR_DISTANCE_METRIC,
    });
    // Index references the bucket by name; make the dependency explicit so the
    // bucket is created first.
    kodiakVectorIndex.addDependency(kodiakVectorBucket);
    kodiakVectorIndex.cfnOptions.deletionPolicy = cdk.CfnDeletionPolicy.RETAIN;
    kodiakVectorIndex.cfnOptions.updateReplacePolicy =
      cdk.CfnDeletionPolicy.RETAIN;

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
    this.vectorBucketName = kodiakVectorBucket.ref;
    new cdk.CfnOutput(this, "KodiakVectorBucketName", {
      value: this.vectorBucketName,
      description:
        "S3 Vectors vector bucket name -- set as KODIAK_VECTOR_BUCKET on the generate Lambda",
    });
    this.vectorBucketArn = kodiakVectorBucket.attrVectorBucketArn;
    new cdk.CfnOutput(this, "KodiakVectorBucketArn", {
      value: this.vectorBucketArn,
      description: "S3 Vectors vector bucket ARN",
    });
    this.vectorIndexName = kodiakVectorIndex.ref;
    new cdk.CfnOutput(this, "KodiakVectorIndexName", {
      value: this.vectorIndexName,
      description:
        "S3 Vectors index name (1024-dim cosine float32) -- set as KODIAK_VECTOR_INDEX on the generate Lambda",
    });
    this.vectorIndexArn = kodiakVectorIndex.attrIndexArn;
    new cdk.CfnOutput(this, "KodiakVectorIndexArn", {
      value: this.vectorIndexArn,
      description: "S3 Vectors index ARN",
    });
  }
}
