import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as cloudfront from "aws-cdk-lib/aws-cloudfront";
import * as route53 from "aws-cdk-lib/aws-route53";
import * as targets from "aws-cdk-lib/aws-route53-targets";
import {
  FRONTIER_ALIASES,
  FRONTIER_API_ORIGIN_DOMAIN,
  FRONTIER_BUCKET_NAME,
  FRONTIER_CERT_ARN,
  FRONTIER_COMMENT,
  FRONTIER_DISTRIBUTION_ID,
  FRONTIER_DOMAIN_NAME,
  FRONTIER_LOG_BUCKET_DOMAIN,
  FRONTIER_LOG_PREFIX,
  FRONTIER_SITE_DOMAIN,
  FRONTIER_ZONE_ID,
  FRONTIER_ZONE_NAME,
} from "./config";

export interface HostingStackProps extends cdk.StackProps {
  readonly projectName: string;
}

// Managed AWS cache/origin-request policies on the live API behaviors.
const CACHING_DISABLED_POLICY_ID = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad";
const ALL_VIEWER_EXCEPT_HOST_HEADER_POLICY_ID =
  "b689b0a8-53d0-40ab-baf2-68738e2966ac";

// API path behaviors on the live distribution, in live order.
const API_BEHAVIOR_PATHS = [
  "/assets/library*",
  "/library/assets*",
  "/localize*",
  "/generate*",
  "/assets/pack*",
  "/campaigns/platform-copy*",
];

/**
 * Kodiak frontier site hosting (issue #202, adoption base = the live
 * hand-made resources, stack id `kodiak-creatives-hosting`). S3 site bucket +
 * CloudFront distribution + origin access control + Route53 alias, all RETAIN.
 *
 * Adopt-in-place, NEVER recreate: the bucket and distribution already exist
 * and serve production traffic. First deploy MUST be `cdk import` (see
 * README); a plain deploy would try to CREATE a duplicate bucket and fail.
 *
 * Construct choice is deliberate, not uniform:
 * - Bucket: L2. Every live property (unversioned, SSE-S3, website docs,
 *   all-false public-access block, BucketOwnerEnforced, public GetObject) is
 *   expressible. One cosmetic delta: L2 renders the public-read statement
 *   without the live `PublicRead` Sid -- drift-detector noise only.
 * - Distribution: L1 CfnDistribution. The live default behavior uses LEGACY
 *   ForwardedValues (no CachePolicyId); L2 CacheBehavior ALWAYS renders a
 *   CachePolicyId (default CACHING_OPTIMIZED), so any L2 distribution would
 *   MODIFY the live distro on first deploy and break the no-op adoption. L1
 *   mirrors live byte-for-byte instead.
 * - OAC: L2 S3OriginAccessControl, provisioned but NOT attached. Attaching it
 *   means swapping the website-endpoint origin for an S3 REST origin plus a
 *   bucket-policy rewrite -- a traffic-affecting cutover that does not belong
 *   in an adoption PR. The follow-up attaches it and locks the bucket down.
 * - DNS alias: L2 ARecord. CloudFormation CANNOT import RecordSets at all, so
 *   the record is context-gated (see below) and joins in a second pass.
 *
 * Explicitly out of scope: content publishing. deploy-frontier.sh keeps the
 * s3 sync + invalidation job; copy tweaks never need a CDK deploy. The
 * kodiak-generate-api origin and the cf-logs bucket are referenced by string
 * only -- owned elsewhere, never managed here.
 */
export class HostingStack extends cdk.Stack {
  public readonly siteBucketName: string;
  public readonly distributionId: string;
  public readonly distributionDomainName: string;

  constructor(scope: Construct, id: string, props: HostingStackProps) {
    super(scope, id, props);

    // ---- site bucket -- LIVE, RETAIN --------------------------------------
    // Public-website bucket: website hosting (index.html + error index.html),
    // public GetObject, SSE-S3, NO public-access block (all false, as live),
    // BucketOwnerEnforced, unversioned.
    // CONVERGE DISCIPLINE (#268, learned 2026-09-08): NEVER delete-bucket-policy
    // on this live bucket to clear the way for the policy CREATE -- CFN CREATE
    // fails with "already exists" against ANY live policy, and every
    // policy-less second is a user-facing 403 (three outages, all mine).
    // Pre-stage converges with `cdk deploy --no-execute`, then delete + execute
    // back-to-back; on ANY 403, restore the policy FIRST via
    // docs/frontier-403-runbook.md and stop -- never fight an in-flight deploy.
    const siteBucket = new s3.Bucket(this, "FrontierSiteBucket", {
      bucketName: FRONTIER_BUCKET_NAME,
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
    // explicitly (DataStack precedent: every stateful resource RETAIN).
    siteBucket.policy?.applyRemovalPolicy(cdk.RemovalPolicy.RETAIN);

    // ---- distribution -- LIVE, RETAIN (L1, verbatim live config) -----------
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
      "FrontierDistribution",
      {
        distributionConfig: {
          enabled: true,
          comment: FRONTIER_COMMENT,
          defaultRootObject: "index.html",
          httpVersion: "http2",
          ipv6Enabled: true,
          priceClass: "PriceClass_100",
          aliases: [...FRONTIER_ALIASES],
          origins: [
            {
              id: "S3-frontier-bryanchasko-com",
              domainName: `${FRONTIER_BUCKET_NAME}.s3-website-${this.region}.amazonaws.com`,
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
            targetOriginId: "S3-frontier-bryanchasko-com",
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
            acmCertificateArn: FRONTIER_CERT_ARN,
            sslSupportMethod: "sni-only",
            minimumProtocolVersion: "TLSv1.2_2021",
          },
          logging: {
            bucket: FRONTIER_LOG_BUCKET_DOMAIN,
            includeCookies: false,
            prefix: FRONTIER_LOG_PREFIX,
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
    // Attaching it is a traffic-affecting cutover (origin swap + bucket policy
    // rewrite), so it ships unattached here and the follow-up wires it.
    const originAccessControl = new cloudfront.S3OriginAccessControl(
      this,
      "FrontierOriginAccessControl",
      {
        originAccessControlName: `${FRONTIER_BUCKET_NAME}-oac`,
        signing: cloudfront.Signing.SIGV4_ALWAYS,
      },
    );
    originAccessControl.applyRemovalPolicy(cdk.RemovalPolicy.RETAIN);

    // ---- DNS alias -- L2, context-gated (default OFF) -----------------------
    // CloudFormation cannot import AWS::Route53::RecordSet, so the record
    // cannot ride along in `cdk import` (its CREATE would fail as a duplicate
    // and roll back the whole adoption). DECISION (#268, verified 2026-09-08):
    // the alias stays HAND-MANAGED, not stack-owned. The zone lives in the
    // website account (aerospaceug-admin), unreachable from the deploy role,
    // and the live record is correct (kodiak.bryanchasko.com A ->
    // d37333alc7ojpl.cloudfront.net = E3GEX8LSRX6OYS). The record is opt-in
    // (`-c hostingIncludeDnsRecord=true`) for use only if the zone ever moves
    // into this account.
    const dnsFlag = this.node.tryGetContext("hostingIncludeDnsRecord");
    // Opt-in (default OFF): a bare deploy must never attempt the cross-account
    // record CREATE. `-c` values arrive as strings, so accept both spellings.
    const includeDnsRecord = dnsFlag === true || dnsFlag === "true";
    if (includeDnsRecord) {
      const zone = route53.HostedZone.fromHostedZoneAttributes(
        this,
        "FrontierZone",
        { hostedZoneId: FRONTIER_ZONE_ID, zoneName: FRONTIER_ZONE_NAME },
      );
      const distroRef = cloudfront.Distribution.fromDistributionAttributes(
        this,
        "FrontierDistributionRef",
        {
          distributionId: FRONTIER_DISTRIBUTION_ID,
          domainName: FRONTIER_DOMAIN_NAME,
        },
      );
      const alias = new route53.ARecord(this, "KodiakAliasRecord", {
        zone,
        recordName: FRONTIER_SITE_DOMAIN,
        target: route53.RecordTarget.fromAlias(
          new targets.CloudFrontTarget(distroRef),
        ),
      });
      alias.applyRemovalPolicy(cdk.RemovalPolicy.RETAIN);
    }

    // ---- tags --------------------------------------------------------------
    // import gate: CFN forbids Tag changes on IMPORT change sets; skip for
    // the CDK_IMPORT_NOTAGS=1 import pass, normal deploys keep the tag.
    if (!process.env.CDK_IMPORT_NOTAGS)
      cdk.Tags.of(this).add("stack", "kodiak-creatives-hosting");

    // ---- outputs -------------------------------------------------------------
    this.siteBucketName = siteBucket.bucketName;
    new cdk.CfnOutput(this, "FrontierSiteBucketName", {
      value: this.siteBucketName,
      description: "Site content bucket -- publish via scripts/deploy-frontier.sh, never via CDK.",
    });
    this.distributionId = distribution.ref;
    new cdk.CfnOutput(this, "FrontierDistributionId", {
      value: this.distributionId,
    });
    this.distributionDomainName = distribution.attrDomainName;
    new cdk.CfnOutput(this, "FrontierDistributionDomainName", {
      value: this.distributionDomainName,
    });
    new cdk.CfnOutput(this, "FrontierSiteUrl", {
      value: `https://${FRONTIER_SITE_DOMAIN}`,
    });
  }
}
