# AgentCore promotion path

poc runs locally with mock fallback. promote to Bedrock AgentCore Runtime in one step:

1. handler wraps run_pipeline(brief, dam_root, out_root) — s3 dam via boto3 s3 sync or Gateway tool
2. create runtime: aws bedrock-agentcore-control create-agent-runtime ...
3. gateway: expose dam list/get + approval webhook as MCP tools via bedrock-agentcore-control create-gateway
4. nova act: browser automation for visual qa — open preview.html at 3 viewports, verify logo/text/brand colors, write back compliance
5. observability: agentcore otel -> cloudwatch, report.jsonl -> s3 vectors for "what drives ctr" learning loop

env: BEDROCK_REGION=us-east-1, BEDROCK_NOVA_CANVAS_MODEL=amazon.nova-canvas-v1:0, BEDROCK_NOVA_TEXT_MODEL=amazon.nova-micro-v1:0
check access: aws bedrock list-foundation-models --region us-east-1 | grep nova
