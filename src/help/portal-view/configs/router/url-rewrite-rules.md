# Router: urlRewriteRules

Rewrite the path with the first matching regex.

**Type:** List of string. **Default:** `[]`.

## Meaning

A list of strings with the form `regex replacement`, separated by a space. The regex matches the incoming path; it does not choose the target host. Both runtimes use a **whole-path match**, apply the first matching rule, and leave unmatched paths unchanged. `$1`, `$2`, and so on refer to captured groups.

## Source examples

```yaml
urlRewriteRules:
  - '/listings/(.*)$ /listing.html?listing=$1'
  - '/ph/uat/de-asia-ekyc-service/v1 /uat-de-asia-ekyc-service/v1'
  - '(/tutorial/.*)/wordpress/(\w+)\.?.*$ $1/cms/$2.php'
```

| Incoming path | Rewritten result | Explanation |
| --- | --- | --- |
| `/listings/123` | `/listing.html?listing=123` | `(.*)` captures `123`; `$1` places it in a query parameter. |
| `/ph/uat/de-asia-ekyc-service/v1` | `/uat-de-asia-ekyc-service/v1` | Removes the exact `/ph/uat` deployment prefix and replaces it with `/uat`. |
| `/tutorial/linux/wordpress/file1` | `/tutorial/linux/cms/file1.php` | `$1` is `/tutorial/linux`; `$2` is `file1`; the rule changes the directory and adds `.php`. |

The second rule matches that exact path, not every child path. To rewrite children, capture and reinsert the suffix explicitly. In the third rule `\w+` captures word characters; the later expression consumes optional punctuation and remaining suffix text. Keep it narrow if backend filenames can contain other characters.

Equivalent source JSON list:

```json
["/listings/(.*)$ /listing.html?listing=$1","/ph/uat/de-asia-ekyc-service/v1 /uat-de-asia-ekyc-service/v1","(/tutorial/.*)/wordpress/(\\w+)\\.?.*$ $1/cms/$2.php"]
```

JSON requires doubled backslashes. In `values.yml`, assign this list to `router.urlRewriteRules`. In resolved `router.yml`, use `urlRewriteRules` as shown above. The Java tests also support JSON text in a quoted scalar; native lists are easier to review.

## Additional examples

```yaml
urlRewriteRules:
  - '/v1/api/(.*) /api/$1'
  - '/old-path /new-path'
```

`/v1/api/orders/42` becomes `/api/orders/42`; `/old-path` becomes `/new-path`. `/old-path/42` does not match the second whole-path rule.

Rust's combined rewrite test uses:

```yaml
urlRewriteRules:
  - '/v1/listings/(.*)$ /listing.html?listing=$1'
methodRewriteRules:
  - '/v1/listings/{id} POST PUT'
queryParamRewriteRules:
  /v1/listings/{id}:
    - oldK: old
      newK: new
```

With target `https://api.example.com/base` and an enabled routing-query override, `POST /v1/listings/123?service_id=svc&old=value` becomes `PUT /base/listing.html?listing=123&new=value`. This demonstrates path captures, method rewriting, target base-path prepending, query-key renaming, and routing-query removal. It is a **Rust test outcome**, not a Java combined-query guarantee.

**Compatibility:** Java and Rust use different regex engines. Keep portable rules to their common syntax; Java look-around and regex backreferences are unsupported in Rust. Java's current URI builder can append a second `?` when a replacement introduces a query and the original request also contains one; Rust merges the replacement and original query pairs. For portable use, avoid combining query-generating URL replacements with existing query strings until that Java behavior is verified/fixed.

The source suggests the [Java regex tester](https://www.freeformatter.com/java-regex-tester.html). It helps check Java matching, but cannot establish Rust compatibility. Rewrites do not change the body, Content-Type, or authorization decisions already made by earlier handlers.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
