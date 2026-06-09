# Cloud bridge (Phase 9 — optional)

This directory holds the AWS SAM template for the optional cloud deployment.
The local stack does not need any of this.

## What lives here

- `template.yaml` — SAM template defining a single Lambda (`RlTrainNightly`)
  triggered by EventBridge Scheduler at 03:00 UTC daily. The Lambda runs the
  containerized `rl` service to train PPO and upload the checkpoint.

## What's missing on purpose

- The Lambda handler. You build a container with the `services/rl` workspace
  member installed, set the entrypoint to `python -m rl.train --steps 100000
  --save /tmp/ppo.zip`, and add an `aws s3 cp` (or `rclone` for R2) step that
  uploads the result.
- DagsHub MLflow tracking. Set `MLFLOW_TRACKING_URI`, `MLFLOW_TRACKING_USERNAME`,
  and `MLFLOW_TRACKING_PASSWORD` as Lambda environment variables and call
  `mlflow.log_artifact()` from `rl.train`.
- Cloudflare R2 vs AWS S3. R2 has no egress fees and a generous free tier.
  AWS S3 free tier caps at 2K PUTs/month — too tight for any real demo. The
  template's `R2_BUCKET` env var leaves the choice open.

## Deploying (when you're ready)

```bash
# build the rl service container
docker build -t urbanguard-rl-train -f infra/docker/python-base.Dockerfile .
# push to ECR public
aws ecr-public create-repository --repository-name urbanguard-rl-train --region us-east-1
docker tag urbanguard-rl-train public.ecr.aws/<your-alias>/urbanguard-rl-train:latest
docker push public.ecr.aws/<your-alias>/urbanguard-rl-train:latest
# deploy
sam deploy --guided \
  --template-file infra/lambda/template.yaml \
  --parameter-overrides ImageUri=public.ecr.aws/<your-alias>/urbanguard-rl-train:latest
```

## Why this is intentionally a stub

The plan says cloud is optional. Phase 9 exists so the architecture story has
a credible "and here's how it would deploy" answer. Wiring a real Lambda needs
an AWS account with billing enabled — that's a decision for after the local
demo is solid.
