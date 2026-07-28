# OSS: DataHub Skill contribution

This tree mirrors the layout expected by [`datahub-project/datahub-skills`](https://github.com/datahub-project/datahub-skills):

```text
skills/breaking-change-remediation/
  SKILL.md
  references/cascade-workflow.md
```

## Upstream PR

**Do not open upstream until coordinated.** An earlier accidental PR ([datahub-project/datahub-skills#63](https://github.com/datahub-project/datahub-skills/pull/63)) was closed with an apology.

Until a real contribution is planned, keep this skill in Cascade only (or copy locally):

## Install locally (Cursor / skills CLI)

```bash
# after upstream merge:
npx skills add datahub-project/datahub-skills

# or copy from this repo:
cp -R oss/datahub-skills/skills/breaking-change-remediation ~/.cursor/skills/breaking-change-remediation
```
