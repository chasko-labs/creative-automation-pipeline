#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { DataStack } from "../lib/data-stack";
import { HostingStack } from "../lib/hosting-stack";
import { GenerateStack } from "../lib/generate-stack";
import { CoachStack } from "../lib/coach-stack";
import { ObservabilityStack } from "../lib/observability-stack";
import { BrowserObservabilityStack } from "../lib/browser-observability-stack";
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

// Reconciled single CDK app for the kodiak creative-automation-pipeline.
//
// Base = the migrated L1 (Cfn*) stacks, generated verbatim from the live
// templates by `cdk migrate` and bound to the live resources by stack id via
// each app's migrate.json Source. The reconciled stacks therefore use the same
// lowercase construct ids the migration produced (kodiak-creatives,
// kodiak-creatives-generate, kodiak-creatives-observability,
// kodiak-creatives-browser-observability) so logical + stack identity match the
// adoption base with zero drift. The retired hand-authored #122 L2 stacks used
// PascalCase ids and are superseded -- do not reintroduce them.
//
// Carried forward from #122: bedrock-logging-stack.ts (both region instances --
// us-east-1 already cdk-managed live, us-west-2 net-new / never-deployed).

// account 946179428633 (bryanchasko-kiro) pinned in config.ts. Allow a
// CDK_DEPLOY_ACCOUNT override for a throwaway/second environment; regions stay
// hard-pinned so the cross-region us-west-2 bedrock instance always lands
// in-account.
const account = process.env.CDK_DEPLOY_ACCOUNT ?? ACCOUNT;

const app = new cdk.App();

// main stack: DAM bucket + dynamodb tables + log bucket + TLS
// bucket policy. all stateful resources RETAIN.
new DataStack(app, "kodiak-creatives", {
  env: { account, region: PRIMARY_REGION },
  projectName: PROJECT_NAME,
  damBucketName: DAM_BUCKET_NAME,
  description:
    "Kodiak creatives main stack: DAM bucket + dynamodb tables + log bucket + TLS policy (stateful RETAIN).",
});

// app log group (RETAIN) + X-Ray sampling rule + observability write policy.
new ObservabilityStack(app, "kodiak-creatives-observability", {
  env: { account, region: PRIMARY_REGION },
  projectName: PROJECT_NAME,
  description:
    "Kodiak creatives observability: app log group (RETAIN) + X-Ray sampling + write policy.",
});

// browser + site-edge telemetry: CloudWatch RUM (X-Ray) + Cognito guest
// identity + CloudFront access-log bucket. New to the reconciled app (#122
// never modeled it).
new BrowserObservabilityStack(app, "kodiak-creatives-browser-observability", {
  env: { account, region: PRIMARY_REGION },
  projectName: PROJECT_NAME,
  description:
    "Kodiak creatives browser observability: CloudWatch RUM + Cognito guest identity + CloudFront access-log bucket.",
});

// container-image generate lambda + public function url + bedrock/S3 IAM.
// FIX 1 (X-Ray ACTIVE + AWS_XRAY_SDK_ENABLED=true + xray:Put* statement) lives
// inside this stack.
new GenerateStack(app, "kodiak-creatives-generate", {
  env: { account, region: PRIMARY_REGION },
  projectName: PROJECT_NAME,
  damBucketName: DAM_BUCKET_NAME,
  description:
    "Kodiak creatives generate endpoint: container lambda + function url + bedrock/S3 IAM + X-Ray ACTIVE (FIX 1).",
});

// bedrock model-invocation logging -- PRIMARY region (us-east-1). Already
// cdk-managed live (stack KodiakCreativesBedrockLoggingUsEast1).
new BedrockLoggingStack(app, "KodiakCreativesBedrockLoggingUsEast1", {
  env: { account, region: PRIMARY_REGION },
  projectName: PROJECT_NAME,
  logGroupName: BEDROCK_LOG_GROUP_NAME,
  roleName: BEDROCK_LOGGING_ROLE_NAME,
  enableSingleton: true,
  description:
    "Kodiak creatives Bedrock model-invocation logging (us-east-1): log group + role (RETAIN) + singleton enable.",
});

// site hosting (#202): S3 bucket + CloudFront distro + OAC + DNS alias, all
// RETAIN, adopted in place. First deploy MUST be `cdk import` (see README) --
// never plain-deploy before import. terminationProtection guards the live site.
new HostingStack(app, "kodiak-creatives-hosting", {
  env: { account, region: PRIMARY_REGION },
  projectName: PROJECT_NAME,
  terminationProtection: true,
  description:
    "Kodiak frontier site hosting: S3 bucket + CloudFront distro + OAC + DNS alias (all RETAIN, adopted in place #202).",
});

// bedrock model-invocation logging in us-west-2, where the custom art-director
// model runs. model-invocation logging is an account+region SINGLETON, so the
// us-east-1 configuration does NOT cover us-west-2 invocations. This second
// instance is net-new (never deployed anywhere) -- carried forward from #122.
// The role name is region-suffixed so it does not collide with the us-east-1
// role (IAM role names are global within an account).
new BedrockLoggingStack(app, "KodiakCreativesBedrockLoggingUsWest2", {
  env: { account, region: BEDROCK_LOGGING_REGION },
  projectName: PROJECT_NAME,
  logGroupName: BEDROCK_LOG_GROUP_NAME,
  roleName: `${BEDROCK_LOGGING_ROLE_NAME}-us-west-2`,
  enableSingleton: true,
  description:
    "Kodiak creatives Bedrock model-invocation logging (us-west-2): log group + role (RETAIN) + singleton enable for the cross-region art-director model.",
});

// campaign coach (Unit 2): Nova Micro /insights + /ask for the creator's
// insights panel + About Q&A. Net-new stack, no imports, no stateful resources.
new CoachStack(app, "kodiak-creatives-coach", {
  env: { account, region: PRIMARY_REGION },
  projectName: PROJECT_NAME,
  description:
    "Kodiak campaign coach: Nova Micro insights + Q&A lambda + public function url (stateless).",
});

// uniform app-level tag set (project/team/managed-by=cdk/repo/environment).
// per-stack stack= tags + the DAM brand=kodiak tag are added inside each stack.
// the migrated L1 templates' repeated inline managed-by=cloudformation tag
// arrays were stripped when lifting the stacks, so nothing conflicts here.
// IMPORT-SAFE (#202): stack-level tags break `cdk import` (CFN forbids Tag
// changes on import change sets). Gated out only for the import pass via
// CDK_IMPORT_NOTAGS=1; normal deploys keep the full tag set.
if (process.env.CDK_IMPORT_NOTAGS !== "1") {
  for (const [k, v] of Object.entries(STANDARD_TAGS)) {
    cdk.Tags.of(app).add(k, v);
  }
}

app.synth();
