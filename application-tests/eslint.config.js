import antfu from '@antfu/eslint-config'
import oxlint from 'eslint-plugin-oxlint'
import playwright from 'eslint-plugin-playwright'

export default antfu(
  { typescript: true },
  {
    ...playwright.configs['flat/recommended'],
    files: ['tests/**'],
  },
)
  // Last, so it switches off the ESLint rules oxlint already checks.
  .append(...oxlint.buildFromOxlintConfigFile('./.oxlintrc.json'))
