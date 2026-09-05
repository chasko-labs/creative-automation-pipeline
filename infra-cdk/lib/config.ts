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
