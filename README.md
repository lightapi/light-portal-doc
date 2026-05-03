# light-portal-doc
Light Portal Documentation

### How to install mdbook?

```
cargo install --git https://github.com/rust-lang/mdBook.git mdbook
```

### How to start the server?

```
mdbook serve -p 4000
```

### How to install mermaid plugin? 

```
cargo install mdbook-mermaid
```

### How to validate portal-view help links?

```
node scripts/validate-portal-help-links.js --portal-view ../portal-view
```

The validator checks that `portal-view` help metadata points to markdown files
in this documentation repo and that the initial owner-scoped pages and
high-value generated forms have contextual help coverage.
