# Query Active Rows

Since we use soft deletes for most tables in the read model, we need to apply an active = true filter to our queries.

For single-table queries, this is straightforward—we can simply add AND active = true to the query. However, for join queries involving multiple tables, the active = true condition must be applied consistently across all participating tables, ideally in an automatic manner.

There are two approaches we can take on top of the current database provider implementation:

### Active in filters

```
    @Override
    public Result<String> queryRolePermission(int offset, int limit, String filtersJson, String globalFilter, String sortingJson, String hostId) {


        boolean isActive = true; // Default to true (active records only)

        // Iterate safely to find and remove the 'active' filter to handle it manually
        if (filters != null) {
            Iterator<Map<String, Object>> it = filters.iterator();
            while (it.hasNext()) {
                Map<String, Object> filter = it.next();
                if ("active".equals(filter.get("id"))) {
                    Object val = filter.get("value");
                    if (val != null) {
                        isActive = Boolean.parseBoolean(val.toString());
                    }
                    it.remove(); // Remove from list so dynamicFilter doesn't add it again
                    break;
                }
            }
        }

        StringBuilder activeSql = new StringBuilder();
        if (isActive) {
            // Strict consistency: A record is only "active" if all related entities are active
            activeSql.append(" AND rp.active = true");
            activeSql.append(" AND r.active = true");
            activeSql.append(" AND ae.active = true");
            activeSql.append(" AND av.active = true");
        } else {
            // Soft-deleted view: Usually we only care that the specific record itself is inactive
            activeSql.append(" AND rp.active = false");
        }

    }	

```

**Pros**

* No need to change the signature, UI and service layer. 

**Cons**

* Need to iterate all filters to find the active flag per call. 


### Active as a seperate parameter

```
    @Override
    public Result<String> queryRolePermission(int offset, int limit, String filtersJson, String globalFilter, String sortingJson, boolean active, String hostId) {
        
        StringBuilder activeSql = new StringBuilder();
        if (active) {
            // Strict consistency: A record is only "active" if all related entities are active
            activeSql.append(" AND rp.active = true");
            activeSql.append(" AND r.active = true");
            activeSql.append(" AND ae.active = true");
            activeSql.append(" AND av.active = true");
        } else {
            // Soft-deleted view: Usually we only care that the specific record itself is inactive
            activeSql.append(" AND rp.active = false");
        }


    }	
```

**Pros**

* Logic is simple in the query. 

**Cons**

* Need to change the service layer and UI to add an additional parameter. 

### Conclusion

