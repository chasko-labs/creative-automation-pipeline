// Shared constants + tag strategy for the kodiak creatives CDK app.
// Single source of truth so every stack agrees on account, regions, resource
// names, and the standard tag set. Ported from the tag blocks that were
// repeated across infra/*.yaml, with managed-by flipped from cloudformation to cdk.

export const ACCOUNT = "946179428633"; // bryanchasko-kiro

// Primary region for everything except the cross-region Bedrock invocation-logging
// dependency (see BEDROCK_LOGGING_REGION / FIX 2 in bedrock-logging-stack.ts).
export const PRIMARY_REGION = "us-east-1";

// The custom art-director model (Nova Pro art-direction + Stability profiles)
// runs in us-west-2, so Bedrock model-invocation logging must be enabled THERE,
// not (only) in us-east-1. This is the region the FIX 2 log group + role live in.
export const BEDROCK_LOGGING_REGION = "us-west-2";

export const PROJECT_NAME = "kodiak-creatives";

// Live DAM bucket - created originally by terraform, adopted by CDK via import.
// us-east-1, account 946179428633. LIVE DATA - never destroy (RemovalPolicy.RETAIN).
export const DAM_BUCKET_NAME = `chasko-creative-dam-${ACCOUNT}-${PRIMARY_REGION}`;
export const DAM_RENDERS_PREFIX = "brands/kodiak/renders/";
// User-upload library prefix (asset_library.py writes uploads here). The
// generate Lambda role's existing DAM grant only covers renders/*, so this
// prefix needs its own grant.
export const DAM_LIBRARY_PREFIX = "brands/kodiak/library/";

// ---- S3 Vectors (first Kodiak vector store) --------------------------------
// Dedicated Amazon S3 Vectors vector bucket + index for the Nova multimodal
// embeddings (amazon.nova-2-multimodal-embeddings-v1:0, 1024 dims, cosine).
// Authored as CDK L1 (aws-s3vectors CfnVectorBucket / CfnIndex) so it is
// IaC-managed from creation -- avoids the drift gap of a hand-created bucket.
// Names are deterministic constants so GenerateStack can build the least-
// privilege ARNs without a cross-stack import.
export const KODIAK_VECTOR_BUCKET_NAME = "kodiak-vectors";
export const KODIAK_VECTOR_INDEX_NAME = "kodiak-assets";
export const KODIAK_VECTOR_DIMENSION = 1024; // matches BEDROCK_EMBED_DIM default
export const KODIAK_VECTOR_DISTANCE_METRIC = "cosine"; // Nova multimodal = cosine
export const KODIAK_VECTOR_DATA_TYPE = "float32"; // only supported S3 Vectors type
// Deterministic S3 Vectors ARNs (us-east-1, account 946179428633). The index
// is a sub-resource of the bucket: bucket/<bucket>/index/<index>.
export const KODIAK_VECTOR_BUCKET_ARN = `arn:aws:s3vectors:${PRIMARY_REGION}:${ACCOUNT}:bucket/${KODIAK_VECTOR_BUCKET_NAME}`;
export const KODIAK_VECTOR_INDEX_ARN = `${KODIAK_VECTOR_BUCKET_ARN}/index/${KODIAK_VECTOR_INDEX_NAME}`;

// Bedrock embedding models the generate Lambda invokes (embeddings.py):
// primary Nova multimodal + Titan text-only fallback.
export const BEDROCK_EMBED_MODEL_ARN = `arn:aws:bedrock:${PRIMARY_REGION}::foundation-model/amazon.nova-2-multimodal-embeddings-v1:0`;
export const BEDROCK_EMBED_FALLBACK_MODEL_ARN = `arn:aws:bedrock:${PRIMARY_REGION}::foundation-model/amazon.titan-embed-text-v2:0`;

// DynamoDB table names (live, RETAIN).
export const LOCALIZATION_MEMORY_TABLE = `${PROJECT_NAME}-localization-memory`;
export const RETAIL_NETWORK_TABLE = `${PROJECT_NAME}-retail-network`;

// Bedrock model-invocation logging destination (FIX 2: us-west-2).
export const BEDROCK_LOG_GROUP_NAME = "/aws/bedrock/kodiak-model-invocations";
export const BEDROCK_LOGGING_ROLE_NAME = "kodiak-bedrock-logging-role";

// App structured-log group + X-Ray sampling rule.
export const APP_LOG_GROUP_NAME = "/kodiak/creative-pipeline";
export const XRAY_SAMPLING_RULE_NAME = "kodiak-creative";

// Standard tag set applied at the app level in bin/app.ts. managed-by=cdk marks
// the migration off the cloudformation/terraform-managed lineage.
export const STANDARD_TAGS: Record<string, string> = {
  project: PROJECT_NAME,
  team: "platform",
  "managed-by": "cdk",
  repo: "chasko-labs/creative-automation-pipeline",
  environment: "production",
};
