# React Schema Form

**React Schema Form** is a form generator based on JSON Schema and form definitions from Light Portal. It renders UI forms to manipulate database entities, and form submissions are automatically hooked into an API endpoint.

## Debugging a Component

Encountering a bug in a `react-schema-form` component can be challenging since the source code may not be directly visible. To debug:

1. Set up the Light Portal server if dropdowns are loaded from the server.
2. Use the example app in the same project to debug.


### Use a Local Alias with Vite

Vite allows creating an alias to point to your library's `src` folder. Update the `vite.config.ts` in your example app:

```javascript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      'react-schema-form': path.resolve(__dirname, '../src'), // Adjust the path to point to the library's `src` folder
    },
  },
});
```

### Use a Link Script in `package.json`

Update the example app's `package.json` file. In the `dependencies` section, replace the library's version with a local path:

```json
{
  "dependencies": {
    "react-schema-form": "file:../src"
  }
}
```

### Library Entry Point

Vite requires an entry point file, typically named `index.js` or `index.ts`, in your library's `src` folder. Ensure that your library's `src` folder includes a properly configured `index.js` file, like this:


```javascript
export { default as SchemaForm } from './SchemaForm'
export { default as ComposedComponent } from './ComposedComponent'
export { default as utils } from './utils'
export { default as Array } from './Array'

```

Without a correctly named and configured entry file, components like `SchemaForm` may not be imported properly.


### Update `index.html`

If you change the entry point file from `main.js` to `index.js`, ensure you update the reference in the `index.html` file located in the root folder. For example:


```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Vite + React</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/index.js"></script>
  </body>
</html>

```

### Sync `devDependencies` from `peerDependencies`

When the source code in `src` is used directly by the example app, the `peerDependencies` in the example app won't work for `react-schema-form` components. To address this, copy the `peerDependencies` into the `devDependencies` section of `react-schema-form`'s `package.json`. For example:


```json
  "devDependencies": {
    "@babel/runtime": "^7.26.0",
    "@codemirror/autocomplete": "^6.18.2",
    "@codemirror/language": "^6.10.6",
    "@codemirror/lint": "^6.8.2",
    "@codemirror/search": "^6.5.7",
    "@codemirror/state": "^6.4.1",
    "@codemirror/theme-one-dark": "^6.1.2",
    "@codemirror/view": "^6.34.2",
    "@emotion/react": "^11.13.5",
    "@emotion/styled": "^11.13.5",
    "@eslint/js": "^9.13.0",
    "@lezer/common": "^1.2.3",
    "@mui/icons-material": "^6.1.6",
    "@mui/material": "^6.1.6",
    "@mui/styles": "^6.1.6",
    "@types/react": "^18.3.1",
    "@uiw/react-markdown-editor": "^6.1.2",
    "@vitejs/plugin-react": "^4.3.3",
    "codemirror": "^6.0.1",
    "eslint": "^9.13.0",
    "eslint-plugin-react": "^7.37.2",
    "eslint-plugin-react-hooks": "^5.0.0",
    "eslint-plugin-react-refresh": "^0.4.14",
    "gh-pages": "^6.2.0",
    "globals": "^15.11.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "vite": "^6.0.3"
  },
  "peerDependencies": {
    "@babel/runtime": "^7.26.0",
    "@codemirror/autocomplete": "^6.18.2",
    "@codemirror/language": "^6.10.6",
    "@codemirror/lint": "^6.8.2",
    "@codemirror/search": "^6.5.7",
    "@codemirror/state": "^6.4.1",
    "@codemirror/theme-one-dark": "^6.1.2",
    "@codemirror/view": "^6.34.2",
    "@emotion/react": "^11.13.5",
    "@emotion/styled": "^11.13.5",
    "@lezer/common": "^1.2.3",
    "@mui/icons-material": "^6.1.6",
    "@mui/material": "^6.1.6",
    "@mui/styles": "^6.1.6",
    "@types/react": "^18.3.1",
    "@uiw/react-markdown-editor": "^6.1.2",
    "codemirror": "^6.0.1",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },

```

Additionally, ensure the `peerDependencies` are also synced with the `dependencies` section of the example app's `package.json`. This step allows `react-schema-form` components to load independently and work seamlessly during development.

### Update Source Code

After completing all the updates, perform a clean install for both `react-schema-form` and the example app. Then, start the server from the example folder using the following command:

```bash
yarn dev
```

Whenever you modify a `react-schema-form` component, simply refresh the browser to reload the example application and see the updated component in action.


### Debug with Visual Studio Code

You can debug the component using Visual Studio Code. There are many tutorials available online that explain how to debug React applications built with Vite, which can help you set up breakpoints, inspect components, and track down issues effectively.


## Component dynaselect

`dynaselect` is a component that renders a dropdown select, either from static options or options loaded dynamically from a server via an API endpoint. It is a wrapper of material ui Autocomplete component. Below is an example form from the example app that demonstrates how to use this component. 

```json
{
  "schema": {
    "type": "object",
    "title": "React Component Autocomplete Demo Static Single",
    "properties": {
      "name": {
        "title": "Name",
        "type": "string",
        "default": "Steve"
      },
      "host": {
        "title": "Host",
        "type": "string"
      },
      "environment": {
        "type": "string",
        "title": "Environment",
        "default": "LOCAL",
        "enum": [
          "LOCAL",
          "SIT1",
          "SIT2",
          "SIT3",
          "UAT1",
          "UAT2"
        ]
      },
      "stringarraysingle": {
        "type": "array",
        "title": "Single String Array",
        "items": {
          "type": "string"
        }
      },
      "stringcat": {
        "type": "string",
        "title": "Joined Strings"
      },
      "stringarraymultiple": {
        "type": "array",
        "title": "Multiple String Array",
        "items": {
          "type": "string"
        }
      }
    },
    "required": [
      "name",
      "environment"
    ]
  },
  "form": [
    "name",
    {
      "key": "host",
      "type": "dynaselect",
      "multiple": false,
      "action": {
        "url": "https://localhost/portal/query?cmd=%7B%22host%22%3A%22lightapi.net%22%2C%22service%22%3A%22user%22%2C%22action%22%3A%22listHost%22%2C%22version%22%3A%220.1.0%22%7D"
      }
    },
    {
      "key": "environment",
      "type": "dynaselect",
      "multiple": false,
      "options": [
        {
          "id": "LOCAL",
          "label": "Local"
        },
        {
          "id": "SIT1",
          "label": "SIT1"
        },
        {
          "id": "SIT2",
          "label": "SIT2"
        },
        {
          "id": "SIT3",
          "label": "SIT3"
        },
        {
          "id": "UAT1",
          "label": "UAT1"
        },
        {
          "id": "UAT2",
          "label": "UAT2"
        }
      ]
    },
    {
      "key": "stringarraysingle",
      "type": "dynaselect",
      "multiple": false,
      "options": [
        {
          "id": "id1",
          "label": "label1"
        },
        {
          "id": "id2",
          "label": "label2"
        },
        {
          "id": "id3",
          "label": "label3"
        },
        {
          "id": "id4",
          "label": "label4"
        },
        {
          "id": "id5",
          "label": "label5"
        },
        {
          "id": "id6",
          "label": "label6"
        }
      ]
    },
    {
      "key": "stringcat",
      "type": "dynaselect",
      "multiple": true,
      "options": [
        {
          "id": "id1",
          "label": "label1"
        },
        {
          "id": "id2",
          "label": "label2"
        },
        {
          "id": "id3",
          "label": "label3"
        },
        {
          "id": "id4",
          "label": "label4"
        },
        {
          "id": "id5",
          "label": "label5"
        },
        {
          "id": "id6",
          "label": "label6"
        }
      ]
    },
    {
      "key": "stringarraymultiple",
      "type": "dynaselect",
      "multiple": true,
      "options": [
        {
          "id": "id1",
          "label": "label1"
        },
        {
          "id": "id2",
          "label": "label2"
        },
        {
          "id": "id3",
          "label": "label3"
        },
        {
          "id": "id4",
          "label": "label4"
        },
        {
          "id": "id5",
          "label": "label5"
        },
        {
          "id": "id6",
          "label": "label6"
        }
      ]
    }
  ]
}
```

### Dynamic Options from APIs

The `host` is a string type field rendered as a `dynaselect` with `multiple` set to `false`. The options for the select are loaded via an API endpoint, with the action URL provided. Note that the `cmd` query parameter value is encoded because it contains curly brackets `{}`.

To encode and decode the query parameter value, you can use the following tool:

[Encoder/Decoder Tool](https://meyerweb.com/eric/tools/dencoder/)


Encoded: 

```
%7B%22host%22%3A%22lightapi.net%22%2C%22service%22%3A%22user%22%2C%22action%22%3A%22listHost%22%2C%22version%22%3A%220.1.0%22%7D
```

Decoded: 

```
{"host":"lightapi.net","service":"user","action":"listHost","version":"0.1.0"}
```

When using the example app to test the `react-schema-form` with APIs, you need to configure CORS on the `light-gateway`. Ensure that CORS is enabled only on the `light-gateway` and not on the backend API, such as `hybrid-query`.

Here is the example in values.yml for the light-gateway. 

```yaml
# cors.yml
cors.enabled: true
cors.allowedOrigins:
  - https://devsignin.lightapi.net
  - https://dev.lightapi.net
  - https://localhost:3000
  - http://localhost:5173
cors.allowedMethods:
  - GET
  - POST
  - PUT
  - DELETE

```
### Single string type

For the `environment` field, the schema defines the type as `string`, and the form definition specifies `multiple: false` to indicate it is a single select.

The select result in the model looks like the following:

```json
{
  "environment": "SIT1",
}
```

### Single string array type

For the `stringarraysingle` field, the schema defines the type as a string array, and the form definition specifies `multiple: false` to indicate it is a single select.

The select result in the model looks like the following:

```json
{
  "stringarraysingle": [
    "id3"
  ],	
}

```

### Multiple string type

For the `stringcat` field, the schema defines the type as a `string`, and the form definition specifies `multiple: true` to indicate it is a multiple select.

The select result in the model looks like the following: 

```json
{
	"stringcat": "id2,id4"
}

```

### Multiple string array type

For the `stringarraymultiple` field, the schema defines the type as a string array, and the form definition specifies `multiple: true` to indicate it is a multiple select.

The select result in the model looks like the following: 

```json
{
  "stringarraymultiple": [
    "id2",
    "id5",
    "id3"
  ],	
}
```

