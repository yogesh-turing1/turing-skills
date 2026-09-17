# Deployed runner reference

## Stable identifiers

- Region: `us-east-1`
- Instance parameter: `/turing/harbor/instance-id`
- Bucket parameter: `/turing/harbor/staging-bucket`
- GLM key parameter: `/turing/harbor/glm-api-key` (`SecureString`)
- GLM base URL parameter: `/turing/harbor/glm-base-url`
- Optional short-lived Google token: `/turing/harbor/gcp-access-token`
- IAM role/profile: `TuringHarborRunnerRole` / `TuringHarborRunnerProfile`
- Security group: `turing-harbor-runner`, intentionally zero ingress
- Budget: `turing-harbor-ec2-monthly`, USD 100/month EC2 compute
- Standard EC2 vCPU quota request: desired 32; may remain pending

Resolve instance and bucket dynamically from Parameter Store. Do not hardcode
their current values into new automation.

## Evidence layout

The submitter stages tasks under:

`s3://BUCKET/tasks/JOB.zip`

The remote runner writes complete Harbor directories under:

- `s3://BUCKET/evidence/JOB/oracle/`
- `s3://BUCKET/evidence/JOB/glm/`

Task staging expires after seven days. Evidence transitions to Standard-IA after
30 days. The bucket blocks all public access, uses default encryption, and has
versioning enabled.

## Known-good acceptance result

- Instance class: `m7i.2xlarge`, 8 vCPU, 32 GiB
- Full Oracle plus five simultaneous GLM attempts: 6m43s
- Oracle: 1.0, zero exceptions
- GLM trials: five complete, zero exceptions
- Peak launch state retained about 26 GiB available RAM
- Compute price observed during setup: USD 0.4032/hour in `us-east-1`

This establishes that `m7i.4xlarge` is not required to meet a ten-minute target
for the representative task. Model/API latency usually dominates after all five
trials run concurrently.

## Monitoring commands

```powershell
$instanceId = aws ssm get-parameter --region us-east-1 `
  --name /turing/harbor/instance-id --query Parameter.Value --output text

aws ec2 describe-instances --region us-east-1 --instance-ids $instanceId `
  --query 'Reservations[0].Instances[0].{State:State.Name,Type:InstanceType}'

aws ssm get-command-invocation --region us-east-1 `
  --command-id COMMAND_ID --instance-id $instanceId
```

After a completed run, download or inspect `result.json` from S3 and enumerate
trial directories. Count a full pass only at reward 1.0.

## Security and lifecycle

- IMDSv2 is required.
- Root EBS is encrypted and persists while the stopped instance exists.
- Instance-initiated shutdown behavior is `stop`.
- A systemd timer stops the host after 45 idle minutes.
- The submission wrapper strips `.pytest_cache`, `__pycache__`, and `*.pyc`.
- Validate no plaintext credential entered local files or remote evidence after
  changing credential or logging behavior.
