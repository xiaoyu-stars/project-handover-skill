/**
 * dsh-project-handover — DeepSeek Harness bundle adapter.
 *
 * Mounts the packaged skill corpus (`<package>/skills/`) through the harness
 * `skills` service, so `skills/project-handover` becomes available like any
 * other skill. Mirrors how `dsh-aris` mounts its corpus:
 *
 *   - the skill root is resolved from this module's own URL, so the package
 *     works identically from node_modules, a git checkout, or a local path;
 *   - `includeDefaultRoots: false` keeps the harness's default roots intact and
 *     only adds this bundle's directory (a project/user skill of the same name
 *     still wins, per the skills provider ranking);
 *   - `@deepseek-ai/dsh-skill-filesystem` is provided by the harness at runtime
 *     (same as dsh-aris), so it is imported bare and not declared as a dependency.
 */

import { fileURLToPath } from 'node:url'
import * as skillFilesystem from '@deepseek-ai/dsh-skill-filesystem'

/** Plugin identity (the package name is what cordis.patch.yml references). */
export const name = 'project-handover-skills'

/** Only the skills service is needed; this bundle registers no tools. */
export const inject = ['skills']

/** `<package>/skills/` — every subdirectory holding a SKILL.md is picked up. */
const SKILL_ROOT = fileURLToPath(new URL('../skills/', import.meta.url))

export async function apply(ctx) {
  await ctx.plugin(skillFilesystem, {
    providerName: 'project-handover',
    includeDefaultRoots: false,
    bundledSkillDir: SKILL_ROOT,
    watch: false,
  })
}
