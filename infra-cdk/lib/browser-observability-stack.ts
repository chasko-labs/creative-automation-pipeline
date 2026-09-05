import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as iam from "aws-cdk-lib/aws-iam";
import * as rum from "aws-cdk-lib/aws-rum";
import * as s3 from "aws-cdk-lib/aws-s3";

export interface BrowserObservabilityStackProps extends cdk.StackProps {
  readonly projectName: string;
  /** RUM app monitor name -- also embedded in the guest role arn scope. */
  readonly rumAppMonitorName?: string;
  /** Live CloudFront domain serving the site (RUM Domain + web-client). */
  readonly siteDomain?: string;
}

/**
 * Kodiak creatives browser + site-edge observability (adoption base = migrated
 * L1, stack id `kodiak-creatives-browser-observability`). CloudWatch RUM with
 * X-Ray tracing + Cognito guest identity + CloudFront access-log bucket.
 *
 * NEW to the reconciled app: #122 never modeled this RUM / Cognito / cf-logs
 * telemetry layer, so it was orphaned. Lifting the migrated L1 stack here + the
 * bin/app.ts instantiation adopts it into the single canonical app.
 *
 * Tagging: inline tag arrays stripped -- app-level tag set (managed-by=cdk)
 * applies; stack= added per-stack here.
 */
export class BrowserObservabilityStack extends cdk.Stack {
  public readonly rumAppMonitorName: string;
  public readonly rumAppMonitorId: string;
  public readonly rumIdentityPoolId: string;
  public readonly rumUnauthRoleArn: string;
  public readonly rumCloudFrontLogBucketName: string;

  constructor(scope: Construct, id: string, props: BrowserObservabilityStackProps) {
    super(scope, id, props);

    const rumAppMonitorName = props.rumAppMonitorName ?? "kodiak-creatives-web";
    const siteDomain = props.siteDomain ?? "d37333alc7ojpl.cloudfront.net";

    // ---- CloudFront standard access-log bucket (versioned, RETAIN) -------
    const rumCloudFrontLogBucket = new s3.CfnBucket(
      this,
      "RumCloudFrontLogBucket",
      {
        bucketName: "kodiak-creatives-cf-logs-946179428633-us-east-1",
        versioningConfiguration: { status: "Enabled" },
        publicAccessBlockConfiguration: {
          blockPublicAcls: true,
          blockPublicPolicy: true,
          ignorePublicAcls: true,
          restrictPublicBuckets: true,
        },
        bucketEncryption: {
          serverSideEncryptionConfiguration: [
            { serverSideEncryptionByDefault: { sseAlgorithm: "AES256" } },
          ],
        },
        ownershipControls: {
          rules: [{ objectOwnership: "BucketOwnerPreferred" }],
        },
      },
    );
    rumCloudFrontLogBucket.cfnOptions.deletionPolicy =
      cdk.CfnDeletionPolicy.RETAIN;
    rumCloudFrontLogBucket.cfnOptions.updateReplacePolicy =
      cdk.CfnDeletionPolicy.RETAIN;

    // ---- Cognito guest identity pool -------------------------------------
    const rumIdentityPool = new cognito.CfnIdentityPool(
      this,
      "RumIdentityPool",
      {
        identityPoolName: "kodiak-creatives-rum",
        allowUnauthenticatedIdentities: true,
      },
    );

    // ---- guest role the RUM web client assumes ---------------------------
    const rumUnauthRole = new iam.CfnRole(this, "RumUnauthRole", {
      assumeRolePolicyDocument: {
        Version: "2012-10-17",
        Statement: [
          {
            Effect: "Allow",
            Principal: { Federated: "cognito-identity.amazonaws.com" },
            Action: "sts:AssumeRoleWithWebIdentity",
            Condition: {
              StringEquals: {
                "cognito-identity.amazonaws.com:aud": rumIdentityPool.ref,
              },
              "ForAnyValue:StringLike": {
                "cognito-identity.amazonaws.com:amr": "unauthenticated",
              },
            },
          },
        ],
      },
      policies: [
        {
          policyName: "rum-put-events",
          policyDocument: {
            Version: "2012-10-17",
            Statement: [
              {
                Sid: "PutRumEvents",
                Effect: "Allow",
                Action: "rum:PutRumEvents",
                Resource: `arn:aws:rum:${this.region}:${this.account}:appmonitor/${rumAppMonitorName}`,
              },
            ],
          },
        },
      ],
    });

    // ---- RUM app monitor (X-Ray enabled) ---------------------------------
    const rumAppMonitor = new rum.CfnAppMonitor(this, "RumAppMonitor", {
      name: rumAppMonitorName,
      domain: siteDomain,
      cwLogEnabled: true,
      appMonitorConfiguration: {
        allowCookies: true,
        enableXRay: true,
        sessionSampleRate: 1,
        telemetries: ["errors", "performance", "http"],
        guestRoleArn: rumUnauthRole.attrArn,
        identityPoolId: rumIdentityPool.ref,
      },
    });

    new cognito.CfnIdentityPoolRoleAttachment(
      this,
      "RumIdentityPoolRoleAttachment",
      {
        identityPoolId: rumIdentityPool.ref,
        roles: { unauthenticated: rumUnauthRole.attrArn },
      },
    );

    // ---- tags ------------------------------------------------------------
    cdk.Tags.of(this).add("stack", "kodiak-creatives-browser-observability");

    // ---- outputs ---------------------------------------------------------
    this.rumAppMonitorName = rumAppMonitor.ref;
    new cdk.CfnOutput(this, "RumAppMonitorName", {
      value: this.rumAppMonitorName,
      description: "RUM app monitor name (Ref returns the name)",
    });
    this.rumAppMonitorId = rumAppMonitor.attrId;
    new cdk.CfnOutput(this, "RumAppMonitorId", {
      value: this.rumAppMonitorId,
      description: "RUM app monitor id (GUID) - the web client's applicationId",
    });
    this.rumIdentityPoolId = rumIdentityPool.ref;
    new cdk.CfnOutput(this, "RumIdentityPoolId", {
      value: this.rumIdentityPoolId,
      description: "Cognito identity pool id for RUM guest creds",
    });
    this.rumUnauthRoleArn = rumUnauthRole.attrArn;
    new cdk.CfnOutput(this, "RumUnauthRoleArn", {
      value: this.rumUnauthRoleArn,
      description: "Guest role arn the RUM web client assumes",
    });
    this.rumCloudFrontLogBucketName = rumCloudFrontLogBucket.ref;
    new cdk.CfnOutput(this, "RumCloudFrontLogBucketName", {
      value: this.rumCloudFrontLogBucketName,
      description: "Destination bucket for CloudFront standard access logs",
    });
    new cdk.CfnOutput(this, "RumWebClientSnippet", {
      value: `cwr('init','APPLICATION_ID_FROM_RumAppMonitorId_output',{ sessionSampleRate:1.0, guestRoleArn:'${rumUnauthRole.attrArn}', identityPoolId:'${rumIdentityPool.ref}', endpoint:'https://dataplane.rum.${this.region}.amazonaws.com', telemetries:['errors','performance','http'], allowCookies:true, enableXRay:true });`,
      description:
        "Frontend embed shape for index.html. Load aws-rum-web (cwr) and init with region us-east-1, applicationId=RumAppMonitorId, guestRoleArn=RumUnauthRoleArn, identityPoolId=RumIdentityPoolId. Fill APPLICATION_ID from the RumAppMonitorId output at deploy time.",
    });
  }
}
