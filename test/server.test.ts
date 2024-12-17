import { server } from '../src/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';

describe('MCP Server', () => {
  let transport: any;

  beforeAll(async () => {
    transport = new StdioServerTransport();
    await server.connect(transport);
  });

  it('should have a handleRequest method', () => {
    expect(transport.handleRequest).toBeDefined();
  });

  it('should fetch a URL using puppeteer and return markdown', async () => {
    const result = await transport.handleRequest({
        method: 'call_tool',
        params: {
            name: 'fetch_url_puppeteer',
            arguments: {
                url: 'https://example.com'
            }
        }
    });
    expect(result).toBeDefined();
    expect(result.content).toBeDefined();
    expect(result.content[0].type).toBe('text');
    expect(result.content[0].text).toContain('# Example Domain');
  });
});