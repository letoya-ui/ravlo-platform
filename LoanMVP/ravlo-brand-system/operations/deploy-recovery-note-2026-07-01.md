# Deploy Recovery Note — 2026-07-01

The app factory in `LoanMVP/app.py` was verified on `main` after recovering from a bad deploy.

Render should deploy from this commit or later.

Verified app factory:

- `LoanMVP.app:create_app()` exists
- schema guard route remains additive only
- construction launch readiness docs remain committed

If Render still reports `Failed to find attribute 'create_app' in 'LoanMVP.app'`, the service is running an older failed commit and should be manually redeployed from the latest `main` commit.
