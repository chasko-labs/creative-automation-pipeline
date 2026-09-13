import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as cloudfront from "aws-cdk-lib/aws-cloudfront";
import {
  DEV_TAGS,
  FRONTIER_API_ORIGIN_DOMAIN,
  FRONTIER_CERT_ARN,
  FRONTIER_LOG_BUCKET_DOMAIN,
  FRONTIER_LOG_PREFIX,
  KODIAK_DEV_ALIASES,
  KODIAK_DEV_BUCKET_NAME,
  KODIAK_DEV_COMMENT,
  KODIAK_DEV_SITE_DOMAIN,
} from "./config";

export interface DevHostingStackProps extends cdk.StackProps {
  readonly projectName: string;
}

// Managed AWS cache/origin-request policies -- same ids the prod HostingStack
// pins on its API behaviors, so dev routes identically.
const CACHING_DISABLED_POLICY_ID = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad";
const ALL_VIEWER_EXCEPT_HOST_HEADER_POLICY_ID =
  "b689b0a8-53d0-40ab-baf2-68738e2966ac";

// API path behaviors -- mirrors the prod distribution's API routing so dev
// behaves like prod (see hosting-stack.ts API_BEHAVIOR_PATHS, same order).
const API_BEHAVIOR_PATHS = [
  "/assets/library*",
  "/library/assets*",
  "/localize*",
  "/generate*",
  "/assets/pack*",
  "/campaigns/platform-copy*",
];

/**
 * Kodiak DEV site hosting (kodiak-dev.bryanchasko.com, stack id
 * `kodiak-creatives-hosting-dev`). NET-NEW: the bucket + distribution do NOT
 * exist yet, so the first deploy is a plain `cdk deploy` create -- NOT
 * `cdk import` (unlike the prod HostingStack, which adopts live resources).
 *
 * Why a separate stack (approach b), not a parameterized HostingStack:
 * the prod HostingStack's distribution is an L1 CfnDistribution modeled
 * byte-for-byte on the live prod distro specifically so `cdk import` is a
 * no-op adoption -- it carries converge-discipline warnings, a verbatim-live
 * comment, and hardcoded FRONTIER_* wiring. Dev is net-new, so it does NOT
 * need (and should not inherit) that verbatim-live constraint. A self-owned
 * dev stack keeps the prod adoption invariants untouched while still mirroring
 * the prod origin/behavior shape.
 *
 * Mirrors prod: S3 website origin + the ApiGw-generate origin, plus the
 * /generate*, /localize*, /library/*, /assets/pack* (etc.) API behaviors, so
 * dev routes like prod. Reuses the prod wildcard cert (*.bryanchasko.com
 * covers kodiak-dev.bryanchasko.com) -- no new cert, no validation record.
 *
 * RETAIN on bucket + distribution, same as prod (safer default). No stack-owned
 * Route53 ARecord: the zone lives in the aerospaceug-admin account, so the dev
 * A-record is hand-created cross-account later -- same gate as prod.
 *
 * ASSUMPTION (per handoff): dev mirrors prod's API routing, so the
 * ApiGw-generate origin + API behaviors are INCLUDED. Dev points at the same
 * FRONTIER_API_ORIGIN_DOMAIN as prod; if a separate dev API origin is wanted
 * later, swap the domain constant.
 */
export class DevHostingStack extends cdk.Stack {
  public readonly siteBucketName: string;
  public readonly distributionId: string;
  public readonly distributionDomainName: string;

  constructor(scope: Construct, id: string, props: DevHostingStackProps) {
    super(scope, id, props);

    // ---- site bucket -- NET-NEW, RETAIN -----------------------------------
    // Public-website bucket mirroring prod's config: website hosting, public
    // GetObject, SSE-S3, no public-access block (all false), BucketOwnerEnforced,
    // unversioned. RETAIN so a stack teardown never silently drops content.
    const siteBucket = new s3.Bucket(this, "DevSiteBucket", {
      bucketName: KODIAK_DEV_BUCKET_NAME,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: new s3.BlockPublicAccess({
        blockPublicAcls: false,
        ignorePublicAcls: false,
        blockPublicPolicy: false,
        restrictPublicBuckets: false,
      }),
      publicReadAccess: true,
      websiteIndexDocument: "index.html",
      websiteErrorDocument: "index.html",
      objectOwnership: s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });
    // L2 does not propagate the bucket's RETAIN to its policy -- set it
    // explicitly (matches prod HostingStack + DataStack precedent).
    siteBucket.policy?.applyRemovalPolicy(cdk.RemovalPolicy.RETAIN);

    // ---- distribution -- NET-NEW, RETAIN (L1, same shape as prod) ----------
    // L1 CfnDistribution to keep the origin/behavior shape identical to prod
    // (prod uses LEGACY ForwardedValues on the default behavior; L2 would
    // always inject a CachePolicyId, diverging from prod). Net-new means there
    // is nothing to adopt, but matching prod's shape keeps dev routing faithful.
    const apiBehavior = (
      pathPattern: string,
    ): cloudfront.CfnDistribution.CacheBehaviorProperty => ({
      pathPattern,
      targetOriginId: "ApiGw-generate",
      viewerProtocolPolicy: "https-only",
      allowedMethods: ["HEAD", "DELETE", "POST", "GET", "OPTIONS", "PUT", "PATCH"],
      cachedMethods: ["HEAD", "GET"],
      compress: true,
      cachePolicyId: CACHING_DISABLED_POLICY_ID,
      originRequestPolicyId: ALL_VIEWER_EXCEPT_HOST_HEADER_POLICY_ID,
    });

    const distribution = new cloudfront.CfnDistribution(
      this,
      "DevDistribution",
      {
        distributionConfig: {
          enabled: true,
          comment: KODIAK_DEV_COMMENT,
          defaultRootObject: "index.html",
          httpVersion: "http2",
          ipv6Enabled: true,
          priceClass: "PriceClass_100",
          aliases: [...KODIAK_DEV_ALIASES],
          origins: [
            {
              id: "S3-kodiak-dev-bryanchasko-com",
              domainName: `${KODIAK_DEV_BUCKET_NAME}.s3-website-${this.region}.amazonaws.com`,
              customOriginConfig: {
                httpPort: 80,
                httpsPort: 443,
                originProtocolPolicy: "http-only",
                originSslProtocols: ["TLSv1", "TLSv1.1", "TLSv1.2"],
                originReadTimeout: 30,
                originKeepaliveTimeout: 5,
              },
              connectionAttempts: 3,
              connectionTimeout: 10,
            },
            {
              id: "ApiGw-generate",
              domainName: FRONTIER_API_ORIGIN_DOMAIN,
              customOriginConfig: {
                httpPort: 80,
                httpsPort: 443,
                originProtocolPolicy: "https-only",
                originSslProtocols: ["TLSv1.2"],
                originReadTimeout: 60,
                originKeepaliveTimeout: 5,
              },
              connectionAttempts: 3,
              connectionTimeout: 10,
            },
          ],
          defaultCacheBehavior: {
            targetOriginId: "S3-kodiak-dev-bryanchasko-com",
            viewerProtocolPolicy: "redirect-to-https",
            allowedMethods: ["HEAD", "GET"],
            cachedMethods: ["HEAD", "GET"],
            compress: true,
            forwardedValues: {
              queryString: false,
              cookies: { forward: "none" },
            },
            minTtl: 0,
            defaultTtl: 86400,
            maxTtl: 31536000,
          },
          cacheBehaviors: API_BEHAVIOR_PATHS.map(apiBehavior),
          viewerCertificate: {
            // Reuse the prod wildcard cert -- *.bryanchasko.com covers
            // kodiak-dev.bryanchasko.com. No new cert, no validation record.
            acmCertificateArn: FRONTIER_CERT_ARN,
            sslSupportMethod: "sni-only",
            minimumProtocolVersion: "TLSv1.2_2021",
          },
          logging: {
            bucket: FRONTIER_LOG_BUCKET_DOMAIN,
            includeCookies: false,
            prefix: `${FRONTIER_LOG_PREFIX}dev/`,
          },
          restrictions: {
            geoRestriction: { restrictionType: "none" },
          },
        },
      },
    );
    distribution.cfnOptions.deletionPolicy = cdk.CfnDeletionPolicy.RETAIN;
    distribution.cfnOptions.updateReplacePolicy = cdk.CfnDeletionPolicy.RETAIN;

    // ---- origin access control: provisioned, NOT attached ------------------
    // Mirrors prod: ships unattached (website-endpoint origin stays), a
    // follow-up wires the S3 REST origin + bucket-policy lockdown.
    const originAccessControl = new cloudfront.S3OriginAccessControl(
      this,
      "DevOriginAccessControl",
      {
        originAccessControlName: `${KODIAK_DEV_BUCKET_NAME}-oac`,
        signing: cloudfront.Signing.SIGV4_ALWAYS,
      },
    );
    originAccessControl.applyRemovalPolicy(cdk.RemovalPolicy.RETAIN);

    // ---- DNS alias -- NOT stack-owned --------------------------------------
    // Same gate as prod: the zone (bryanchasko.com) lives in the
    // aerospaceug-admin account, unreachable from this deploy role. The dev
    // A-record (kodiak-dev.bryanchasko.com A -> <this distro>) is hand-created
    // cross-account after deploy. This stack deliberately owns NO ARecord.

    // ---- tags --------------------------------------------------------------
    // Dev tag set (environment=development). Applied at the stack level, not
    // app-wide, so it does not disturb the production app tags in bin/app.ts.
    for (const [k, v] of Object.entries(DEV_TAGS)) {
      cdk.Tags.of(this).add(k, v);
    }
    cdk.Tags.of(this).add("stack", "kodiak-creatives-hosting-dev");

    // ---- outputs -----------------------------------------------------------
    this.siteBucketName = siteBucket.bucketName;
    new cdk.CfnOutput(this, "DevSiteBucketName", {
      value: this.siteBucketName,
      description:
        "Dev site content bucket -- publish site bytes here (never via CDK).",
    });
    this.distributionId = distribution.ref;
    new cdk.CfnOutput(this, "DevDistributionId", {
      value: this.distributionId,
    });
    this.distributionDomainName = distribution.attrDomainName;
    new cdk.CfnOutput(this, "DevDistributionDomainName", {
      value: this.distributionDomainName,
      description:
        "Point the hand-created cross-account kodiak-dev A-record at this CloudFront domain.",
    });
    new cdk.CfnOutput(this, "DevSiteUrl", {
      value: `https://${KODIAK_DEV_SITE_DOMAIN}`,
    });
  }
}
