# search-fetch-server MCP Server

A Model Context Protocol server

This is a TypeScript-based MCP server that implements a simple notes system. It demonstrates core MCP concepts by providing:

- Resources representing text notes with URIs and metadata
- Tools for creating new notes, fetching URLs, and performing searches
- Prompts for generating summaries of notes

## Features

### Resources
- List and access notes via `note://` URIs
- Each note has a title, content and metadata
- Plain text mime type for simple content access

### Tools
- `create_note` - Create new text notes
  - Takes title and content as required parameters
  - Stores note in server state
- `fetch_url` - Fetch content from a URL and optionally convert to markdown using Puppeteer
  - Takes a URL as a required parameter
  - Takes an optional `use_puppeteer` boolean parameter. If true, it will use puppeteer with `waitUntil` set to `networkidle2` and a timeout of 30 seconds. Otherwise, it will use axios.
  - Returns the content of the URL as markdown if using puppeteer, otherwise returns the content as is.
- `duckduckgo_search` - Perform a DuckDuckGo search
  - Takes a query as a required parameter
  - Returns search results as a JSON string

### Prompts
- `summarize_notes` - Generate a summary of all stored notes
  - Includes all note contents as embedded resources
  - Returns structured prompt for LLM summarization

## Development

Install dependencies:
```bash
npm install
```

Build the server:
```bash
npm run build
```

For development with auto-rebuild:
```bash
npm run watch
```

## Installation

To use with Claude Desktop, add the server config:

On MacOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
On Windows: `%APPDATA%/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "search-fetch-server": {
      "command": "node",
      "args": ["/path/to/search-fetch-server/build/index.js"]
    }
  }
}
```

### Debugging

Since MCP servers communicate over stdio, debugging can be challenging. We recommend using the [MCP Inspector](https://github.com/modelcontextprotocol/inspector), which is available as a package script:

```bash
npm run inspector
```

The Inspector will provide a URL to access debugging tools in your browser.
