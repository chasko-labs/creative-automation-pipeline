#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { DataStack } from "../lib/data-stack";
import { GenerateStack } from "../lib/generate-stack";
import { ObservabilityStack } from "../lib/observability-stack";
import { BedrockLoggingStack } from "../lib/bedrock-logging-stack";
import {
  ACCOUNT,
  PRIMARY_REGION,
  BEDROCK_LOGGING_REGION,
  PROJECT_NAME,
  DAM_BUCKET_NAME,
  BEDROCK_LOG_GROUP_NAME,
  BEDROCK_LOGGING_ROLE_NAME,
  STANDARD_TAGS,
} from "../lib/config";

// account 946179428633 (bryanchasko-kiro) pinned in config.ts. Allow a
// CDK_DEPLOY_ACCOUNT override for a throwaway/second environment; region stays
// hard-pinned so the cross-region us-west-2 instance always lands in-account.
const account = process.env.CDK_DEPLOY_ACCOUNT ?? ACCOUNT;

const app = new cdk.App();

// stateful data: DAM bucket (import-safe) + dynamodb tables. all RETAIN.
new DataStack(app, "KodiakCreativesData", {
  env: { account, region: PRIMARY_REGION },
  projectName: PROJECT_NAME,
  damBucketName: DAM_BUCKET_NAME,
  description:
    "Kodiak creatives stateful data: DAM bucket + dynamodb tables (all RETAIN).",
});

// app log group + X-Ray sampling rule + observability write policy.
new ObservabilityStack(app, "KodiakCreativesObservability", {
  env: { account, region: PRIMARY_REGION },
  projectName: PROJECT_NAME,
  description:
    "Kodiak creatives observability: app log group + X-Ray sampling + write policy.",
});

// container-image generate lambda + public function url + bedrock/S3 IAM.
// FIX 1 (X-Ray ACTIVE) lives inside this stack.
new GenerateStack(app, "KodiakCreativesGenerate", {
  env: { account, region: PRIMARY_REGION },
  projectName: PROJECT_NAME,
  damBucketName: DAM_BUCKET_NAME,
  description:
    "Kodiak creatives generate endpoint: container lambda + function url + bedrock/S3 IAM.",
});

// bedrock model-invocation logging -- PRIMARY region (us-east-1).
new BedrockLoggingStack(app, "KodiakCreativesBedrockLoggingUsEast1", {
  env: { account, region: PRIMARY_REGION },
  projectName: PROJECT_NAME,
  logGroupName: BEDROCK_LOG_GROUP_NAME,
  roleName: BEDROCK_LOGGING_ROLE_NAME,
  enableSingleton: true,
  description:
    "Kodiak creatives Bedrock model-invocation logging (us-east-1): log group + role + singleton enable.",
});

// FIX 2 -- bedrock model-invocation logging in us-west-2, where the custom
// art-director model actually runs. model-invocation logging is an
// account+region SINGLETON, so the us-east-1 configuration does NOT cover
// us-west-2 invocations. a second instance provisions a us-west-2 log group +
// a us-west-2-scoped role and enables the singleton in that region too. the
// role name is region-suffixed so it does not collide with the us-east-1 role
// (IAM role names are global within an account).
new BedrockLoggingStack(app, "KodiakCreativesBedrockLoggingUsWest2", {
  env: { account, region: BEDROCK_LOGGING_REGION },
  projectName: PROJECT_NAME,
  logGroupName: BEDROCK_LOG_GROUP_NAME,
  roleName: `${BEDROCK_LOGGING_ROLE_NAME}-us-west-2`,
  enableSingleton: true,
  description:
    "Kodiak creatives Bedrock model-invocation logging (us-west-2, FIX 2): log group + role + singleton enable for the cross-region art-director model.",
});

// standard tag set applied app-wide (project/team/managed-by/repo/environment).
// per-stack stack= tags are added inside each stack.
for (const [k, v] of Object.entries(STANDARD_TAGS)) {
  cdk.Tags.of(app).add(k, v);
}

app.synth();
