import antfu from '@antfu/eslint-config'
import oxlint from 'eslint-plugin-oxlint'

export default antfu({ vue: true, typescript: true })
  // Last, so it switches off the ESLint rules oxlint already checks.
  .append(...oxlint.buildFromOxlintConfigFile('.oxlintrc.json'))
