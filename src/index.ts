#!/usr/bin/env node

/**
 * This is a template MCP server that implements a simple notes system.
 * It demonstrates core MCP concepts like resources and tools by allowing:
 * - Listing notes as resources
 * - Reading individual notes
 * - Creating new notes via a tool
 * - Summarizing all notes via a prompt
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListResourcesRequestSchema,
  ListToolsRequestSchema,
  ReadResourceRequestSchema,
  ListPromptsRequestSchema,
  GetPromptRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import axios from 'axios';
import * as urllib from 'url';
import * as cheerio from 'cheerio';
import puppeteer from 'puppeteer';
import { JSDOM } from 'jsdom';
import TurndownService from 'turndown';

/**
 * Type alias for a note object.
 */
type Note = { title: string, content: string };

/**
 * Simple in-memory storage for notes.
 * In a real implementation, this would likely be backed by a database.
 */
const notes: { [id: string]: Note } = {
  "1": { title: "First Note", content: "This is note 1" },
  "2": { title: "Second Note", content: "This is note 2" }
};

/**
 * Create an MCP server with capabilities for resources (to list/read notes),
 * tools (to create new notes), and prompts (to summarize notes).
 */
export const server = new Server(
  {
    name: "search-fetch-server",
    version: "0.1.0",
  },
  {
    capabilities: {
      resources: {},
      tools: {},
      prompts: {},
    },
  }
);

/**
 * Handler for listing available notes as resources.
 * Each note is exposed as a resource with:
 * - A note:// URI scheme
 * - Plain text MIME type
 * - Human readable name and description (now including the note title)
 */
server.setRequestHandler(ListResourcesRequestSchema, async () => {
  return {
    resources: Object.entries(notes).map(([id, note]) => ({
      uri: `note:///${id}`,
      mimeType: "text/plain",
      name: note.title,
      description: `A text note: ${note.title}`
    }))
  };
});

/**
 * Handler for reading the contents of a specific note.
 * Takes a note:// URI and returns the note content as plain text.
 */
server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const url = new URL(request.params.uri);
  const id = url.pathname.replace(/^\//, '');
  const note = notes[id];

  if (!note) {
    throw new Error(`Note ${id} not found`);
  }

  return {
    contents: [{
      uri: request.params.uri,
      mimeType: "text/plain",
      text: note.content
    }]
  };
});

/**
 * Handler that lists available tools.
 * Exposes a single "create_note" tool that lets clients create new notes.
 */
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "create_note",
        description: "Create a new note",
        inputSchema: {
          type: "object",
          properties: {
            title: {
              type: "string",
              description: "Title of the note"
            },
            content: {
              type: "string",
              description: "Text content of the note"
            }
          },
          required: ["title", "content"]
        }
      },
      {
        name: "fetch_url",
        description: "Fetch content from a URL. Supports optional use of Puppeteer with custom flags.",
        inputSchema: {
          type: "object",
          properties: {
            url: {
              type: "string",
              description: "The URL to fetch content from"
            },
            usePuppeteer: {
              type: "boolean",
              description: "Whether to use Puppeteer to fetch the URL (default: true)",
              default: true
            },
            puppeteerFlags: {
              type: "string",
              description: "Custom flags to pass to Puppeteer (optional)"
            },
            puppeteerHeadless: {
              type: "boolean",
              description: "Whether to run Puppeteer in headless mode (default: false)",
              default: false
            },
            raw: {
              type: "boolean",
              description: "Whether to return the raw content without converting to Markdown (default: false)",
              default: false
            }
          },
          required: ["url"]
        }
      },
      {
        name: "duckduckgo_search",
        description: "Perform a DuckDuckGo search",
        inputSchema: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description: "Search query"
            },
            num_results: {
                type: "number",
                description: "Number of results to return (default: 5)",
                default: 5
            }
          },
          required: ["query"]
        }
      }
    ]
  };
});

/**
 * Handler for the create_note tool.
 * Creates a new note with the provided title and content, and returns success message.
 */
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  switch (request.params.name) {
    case "create_note": {
      const title = String(request.params.arguments?.title);
      const content = String(request.params.arguments?.content);
      if (!title || !content) {
        throw new Error("Title and content are required");
      }

      const id = String(Object.keys(notes).length + 1);
      notes[id] = { title, content };

      return {
        content: [{
          type: "text",
          text: `Created note ${id}: ${title}`
        }]
      };
    }
    case "fetch_url": {
        const url = String(request.params.arguments?.url);
        const usePuppeteer = request.params.arguments?.usePuppeteer === undefined ? true : request.params.arguments?.usePuppeteer;
        const puppeteerFlags = String(request.params.arguments?.puppeteerFlags || '');
        const puppeteerHeadless = request.params.arguments?.puppeteerHeadless === undefined ? false : request.params.arguments?.puppeteerHeadless;
        const raw = request.params.arguments?.raw === undefined ? false : request.params.arguments?.raw;
        
        if (!url) {
          throw new Error("URL is required");
        }
    
        const turndownService = new TurndownService();
        if (usePuppeteer) {
          try {
            const launchOptions: any = { headless: puppeteerHeadless };
            if (puppeteerFlags) {
              launchOptions.args = [...(launchOptions.args || []), ...puppeteerFlags.split(' ')];
            }
    
            const browser = await puppeteer.launch(launchOptions);
            const page = await browser.newPage();
            await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
            const html = await page.content();
            await browser.close();
    
            if (raw) {
              return {
                content: [{
                  type: "text",
                  text: html
                }]
              };
            } else {
              const markdown = turndownService.turndown(html);
              return {
                content: [{
                  type: "text",
                  text: markdown
                }]
              };
            }
          } catch (error: any) {
            console.error(`Puppeteer error: ${error.message}`);
            // Fallback to axios is handled below
          }
        }
    
        // Fallback to axios if usePuppeteer is false or if Puppeteer fails
        try {
          const response = await axios.get(url);
          if (raw) {
            return {
              content: [{
                type: "text",
                text: response.data
              }]
            };
          } else {
            const markdown = turndownService.turndown(response.data);
            return {
              content: [{
                type: "text",
                text: markdown
              }]
            };
          }
        } catch (axiosError: any) {
          return {
            content: [{
              type: "text",
              text: `Error fetching URL: ${usePuppeteer ? 'Puppeteer error (see above), ' : ''}Axios fallback error: ${axiosError.message}`
            }],
            isError: true
          };
        }
      }
    case "duckduckgo_search": {
        const query = String(request.params.arguments?.query);
        const numResults = Number(request.params.arguments?.num_results) || 5;
        if (!query) {
            throw new Error("Query is required");
        }
        try {
            const encodedQuery = urllib.format( { pathname: query } );
            const url = `https://html.duckduckgo.com/html/?q=${encodedQuery}`;
            const headers = {
                'User-Agent':
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            };
            const response = await axios.get(url, { headers });
            const $ = cheerio.load(response.data);
            const results: { title: string, url: string, description: string }[] = [];
            $('.result').slice(0, numResults).each((i, el) => {
                const titleElem = $(el).find('a.result__a');
                const link = titleElem.attr('href');
                const title = titleElem.text();
                const snippet = $(el).find('a.result__snippet');
                const description = snippet.text();
                if (title && link) {
                    let canonicalUrl = link;
                    if (link.includes('duckduckgo.com/l/?uddg=')) {
                        canonicalUrl = urllib.parse(link, true).query.uddg as string;
                        if (canonicalUrl.includes('&rut=')) {
                            canonicalUrl = canonicalUrl.split('&rut=')[0];
                        }
                    }
                    results.push({
                        title,
                        url: canonicalUrl,
                        description
                    });
                }
            });
            return {
                content: [{
                    type: "text",
                    text: JSON.stringify(results, null, 2)
                }]
            };
        } catch (error: any) {
            return {
                content: [{
                    type: "text",
                    text: `Error performing search: ${error.message}`
                }],
                isError: true
            };
        }
    }
    default:
      throw new Error("Unknown tool");
  }
});

/**
 * Handler that lists available prompts.
 * Exposes a single "summarize_notes" prompt that summarizes all notes.
 */
server.setRequestHandler(ListPromptsRequestSchema, async () => {
  return {
    prompts: [
      {
        name: "summarize_notes",
        description: "Summarize all notes",
      }
    ]
  };
});

/**
 * Handler for the summarize_notes prompt.
 * Returns a prompt that requests summarization of all notes, with the notes' contents embedded as resources.
 */
server.setRequestHandler(GetPromptRequestSchema, async (request) => {
  if (request.params.name !== "summarize_notes") {
    throw new Error("Unknown prompt");
  }

  const embeddedNotes = Object.entries(notes).map(([id, note]) => ({
    type: "resource" as const,
    resource: {
      uri: `note:///${id}`,
      mimeType: "text/plain",
      text: note.content
    }
  }));

  return {
    messages: [
      {
        role: "user",
        content: {
          type: "text",
          text: "Please summarize the following notes:"
        }
      },
      ...embeddedNotes.map(note => ({
        role: "user" as const,
        content: note
      })),
      {
        role: "user",
        content: {
          type: "text",
          text: "Provide a concise summary of all the notes above."
        }
      }
    ]
  };
});

/**
 * Start the server using stdio transport.
 * This allows the server to communicate via standard input/output streams.
 */
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
    console.log("Server started");
}

main().catch((error: any) => {
  console.error("Server error:", error);
  process.exit(1);
});
