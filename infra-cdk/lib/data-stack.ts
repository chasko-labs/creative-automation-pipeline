import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";

export interface DataStackProps extends cdk.StackProps {
  readonly projectName: string;
  readonly damBucketName: string;
}

/**
 * Stateful data for the Kodiak creative pipeline.
 *
 * Every resource here is LIVE and holds production data, so every resource
 * carries RemovalPolicy.RETAIN -- a stack delete never destroys the bucket or
 * the tables. The DAM bucket already exists (terraform-created, then CFN
 * import-modeled in ../infra/import-dam.yaml); creating it fresh would collide
 * on the globally-unique name. Adopt it into this stack with `cdk import`
 * (see README) -- the modeled properties below mirror the live bucket exactly
 * so the import validates with zero drift.
 */
export class DataStack extends cdk.Stack {
  public readonly damBucket: s3.IBucket;
  public readonly localizationMemoryTable: dynamodb.ITable;
  public readonly retailNetworkTable: dynamodb.ITable;

  constructor(scope: Construct, id: string, props: DataStackProps) {
    super(scope, id, props);

    const { projectName, damBucketName } = props;

    // ---- DAM bucket -------------------------------------------------------
    // properties mirror the live bucket byte-for-byte so `cdk import` adopts it
    // without a replace: versioned, aws:kms SSE + bucket-key, full public-access
    // block, lifecycle (abort MPU 7d + renders tiering). NOTE the live bucket
    // uses aws:kms (S3-managed KMS default key) with bucketKeyEnabled, NOT
    // plain SSE-S3 -- ported from the live template.yaml / import-dam.yaml, not
    // the (stale) s3-dam.tf default.
    const damBucket = new s3.Bucket(this, "StyleLibraryBucket", {
      bucketName: damBucketName,
      versioned: true,
      encryption: s3.BucketEncryption.KMS_MANAGED,
      bucketKeyEnabled: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true, // adds the DenyInsecureTransport (aws:SecureTransport=false) bucket policy
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      lifecycleRules: [
        {
          id: "abort-multipart",
          enabled: true,
          abortIncompleteMultipartUploadAfter: cdk.Duration.days(7),
        },
        {
          id: "renders-archive",
          enabled: true,
          prefix: "brands/kodiak/renders/",
          transitions: [
            {
              storageClass: s3.StorageClass.INFREQUENT_ACCESS,
              transitionAfter: cdk.Duration.days(90),
            },
            {
              storageClass: s3.StorageClass.GLACIER,
              transitionAfter: cdk.Duration.days(180),
            },
            {
              storageClass: s3.StorageClass.DEEP_ARCHIVE,
              transitionAfter: cdk.Duration.days(365),
            },
          ],
          noncurrentVersionTransitions: [
            {
              storageClass: s3.StorageClass.INFREQUENT_ACCESS,
              transitionAfter: cdk.Duration.days(30),
              noncurrentVersionsToRetain: 2,
            },
          ],
        },
      ],
    });
    this.damBucket = damBucket;

    // ---- DynamoDB: localization memory -----------------------------------
    // one row per creative per place. PK market, SK place_message_id. PITR on.
    const localizationMemoryTable = new dynamodb.Table(
      this,
      "LocalizationMemoryTable",
      {
        tableName: `${projectName}-localization-memory`,
        partitionKey: { name: "market", type: dynamodb.AttributeType.STRING },
        sortKey: {
          name: "place_message_id",
          type: dynamodb.AttributeType.STRING,
        },
        billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
        pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
        removalPolicy: cdk.RemovalPolicy.RETAIN,
      },
    );
    this.localizationMemoryTable = localizationMemoryTable;

    // ---- DynamoDB: retail network ----------------------------------------
    // one row per storefront. PK store_id. GSI byMarket (HASH market, project all).
    const retailNetworkTable = new dynamodb.Table(this, "RetailNetworkTable", {
      tableName: `${projectName}-retail-network`,
      partitionKey: { name: "store_id", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });
    retailNetworkTable.addGlobalSecondaryIndex({
      indexName: "byMarket",
      partitionKey: { name: "market", type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });
    this.retailNetworkTable = retailNetworkTable;

    // ---- tags -------------------------------------------------------------
    // project/team/managed-by/repo/environment come from the app-level tag set
    // (bin/app.ts). brand + stack are DataStack-specific.
    cdk.Tags.of(this).add("brand", "kodiak");
    cdk.Tags.of(this).add("stack", "kodiak-creatives-data");

    // ---- outputs ----------------------------------------------------------
    new cdk.CfnOutput(this, "StyleLibraryBucketName", {
      value: damBucket.bucketName,
      description:
        "Cloud storage bucket - use as DAM_S3_BUCKET with prefix brands/kodiak/",
    });
    new cdk.CfnOutput(this, "StyleLibraryPrefix", { value: "brands/kodiak/" });
    new cdk.CfnOutput(this, "LocalizationMemoryTableName", {
      value: localizationMemoryTable.tableName,
    });
    new cdk.CfnOutput(this, "RetailNetworkTableName", {
      value: retailNetworkTable.tableName,
    });
  }
}
