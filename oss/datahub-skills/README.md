# OSS: DataHub Skill contribution

This tree mirrors the layout expected by [`datahub-project/datahub-skills`](https://github.com/datahub-project/datahub-skills):

```text
skills/breaking-change-remediation/
  SKILL.md
  references/cascade-workflow.md
```

## Upstream PR

Opened against `datahub-project/datahub-skills`:

**https://github.com/datahub-project/datahub-skills/pull/63**

Until merged, agents can point at this repo path or copy the folder into a local skills install.

## Install locally (Cursor / skills CLI)

```bash
# after upstream merge:
npx skills add datahub-project/datahub-skills

# or copy from this repo:
cp -R oss/datahub-skills/skills/breaking-change-remediation ~/.cursor/skills/breaking-change-remediation
```
