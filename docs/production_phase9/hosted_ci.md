# Hosted verification history

The fresh GitHub run for `f3a63c5` passed locked builds, quality, offline regression/contracts and staging/recovery. Its scanner step failed before assessment because the scanner could not read the exported image archive on Linux (`permission denied`). [Retained run](https://github.com/pranjalrmcf/Blackgrid/actions/runs/39948840807).

The workflow now explicitly gives the **public runtime-image archive** mode 0644 before mounting it read-only into the capability-restricted scanner. Dropping all capabilities prevents the scanner from overriding a different file owner's permissions, even with UID 0. No production data, credential, Docker-socket access or privileged execution is added. Scan scope, digest, security thresholds and freshness gates are unchanged. This fixes a CI file-permission difference previously hidden by the Windows Docker bind mount, not an application or scientific failure. The failed run and uploaded synthetic test evidence remain retained on GitHub.

The local acceptance record remains a record of local execution; hosted results belong to their exact source commit and are available in GitHub Actions.
