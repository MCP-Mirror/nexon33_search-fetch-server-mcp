import { server } from '../build/index.js';
describe('MCP Server', () => {
    it('should have a handleRequest method', () => {
        expect(server.handleRequest).toBeDefined();
    });
});
