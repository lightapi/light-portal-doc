# Handler Config

Use the handler config to define which handlers are available, how handler chains are composed, and which chain runs for each request path.

Common properties:

- `handlers`: handler aliases enabled for this gateway
- `chains`: named handler chains
- `paths`: request path and method mappings
- `defaultHandlers`: fallback chain when no path entry matches

