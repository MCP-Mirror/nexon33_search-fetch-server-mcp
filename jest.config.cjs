/** @type {import('ts-jest').JestConfigWithTsJest} */
module.exports = {
  testEnvironment: 'node',
  testEnvironmentOptions: {
    "experimentalVmModules": true
  },
  testMatch: ['<rootDir>/test/**/*.test.ts'],
  moduleNameMapper: {
    '../src/index.js': '<rootDir>/src/index.ts',
  },
  transform: {
    '^.+\\.tsx?$': 'babel-jest',
    '^.+\\.m?js$': 'babel-jest',
  },
  moduleFileExtensions: ['js', 'ts', 'tsx', 'json'],
  transformIgnorePatterns: [
    '/node_modules/(?!@modelcontextprotocol/sdk|@modelcontextprotocol/sdk/.*|.*\\.mjs$)',
  ],
};