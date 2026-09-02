terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 5.0" }
  }
}

variable "bucket_name" {
  description = "DAM bucket name — set DAM_S3_BUCKET env or pass -var bucket_name=..."
  type        = string
  default     = "chasko-creative-dam-dev"
}
variable "region" { default = "us-east-1" }
variable "versioning" { default = true }

provider "aws" { region = var.region }

resource "aws_s3_bucket" "dam" {
  bucket = var.bucket_name
  tags   = { project = "creative-automation-pipeline", brand = "kodiak", managed = "terraform" }
}

resource "aws_s3_bucket_versioning" "dam" {
  bucket = aws_s3_bucket.dam.id
  versioning_configuration { status = var.versioning ? "Enabled" : "Suspended" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "dam" {
  bucket = aws_s3_bucket.dam.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "aws:kms" }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "dam" {
  bucket                  = aws_s3_bucket.dam.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "dam" {
  bucket = aws_s3_bucket.dam.id
  rule {
    id     = "abort-multipart"
    status = "Enabled"
    filter { prefix = "" }
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
  }
  rule {
    id     = "renders-archive"
    status = "Enabled"
    filter { prefix = "brands/kodiak/renders/" }
    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
    transition {
      days          = 180
      storage_class = "GLACIER"
    }
    transition {
      days          = 365
      storage_class = "DEEP_ARCHIVE"
    }
    noncurrent_version_transition {
      newer_noncurrent_versions = 2
      noncurrent_days           = 30
      storage_class             = "STANDARD_IA"
    }
  }
}

resource "aws_s3_bucket_policy" "dam_tls_only" {
  bucket = aws_s3_bucket.dam.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = ["${aws_s3_bucket.dam.arn}", "${aws_s3_bucket.dam.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
}

output "bucket" { value = aws_s3_bucket.dam.bucket }
output "prefix_brands" { value = "brands/kodiak/" }
output "env_hint" { value = "export DAM_S3_BUCKET=${aws_s3_bucket.dam.bucket} DAM_S3_PREFIX=brands/kodiak/" }
