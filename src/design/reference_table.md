# Reference Table

When building a web application, there would be a lot of dropdown selects in forms. The form itself only cares about the `id` and `label` list to render the form and only the `id` will be submitted to the backend API for single select and several `ids` for multiple select. 

To save the effort to create many similar tables, we can craete a set of tables for all dropdowns. For some of the reference tables, dropdown should be the same across all hosts and we can set common flag to 'Y' so that they are shared by all hosts. If the dropdown values might be different between hosts, we can create a reference table per host and link the reference table with host in a separate table that support sharding. 

## Reference Schema

```
CREATE TABLE ref_host_t (
  table_id             VARCHAR(22) NOT NULL,
  host_id              VARCHAR(22) NOT NULL,
  PRIMARY KEY (table_id, host_id),
  FOREIGN KEY (table_id) REFERENCES ref_table_t (table_id) ON DELETE CASCADE,
  FOREIGN KEY (host_id) REFERENCES host (host_id) ON DELETE CASCADE
);

CREATE TABLE ref_table_t (
  table_id             VARCHAR(22) NOT NULL, -- UUID genereated by Util
  table_name           VARCHAR(80) NOT NULL, -- Name of the ref table for lookup.
  table_desc           VARCHAR(1024) NULL,
  active               CHAR(1) NOT NULL DEFAULT 'Y', -- Only active table returns values
  editable             CHAR(1) NOT NULL DEFAULT 'Y', -- Table value and locale can be updated via ref admin
  common               CHAR(1) NOT NULL DEFAULT 'Y', -- The drop down shared across hosts
  PRIMARY KEY(table_id)
);


CREATE TABLE ref_value_t (
  value_id              VARCHAR(22) NOT NULL,
  table_id              VARCHAR(22) NOT NULL,
  value_code            VARCHAR(80) NOT NULL, -- The dropdown value
  start_time            TIMESTAMP NULL,       
  end_time              TIMESTAMP NULL,
  display_order         INT,                  -- for editor and dropdown list.
  active                VARCHAR(1) NOT NULL DEFAULT 'Y',
  PRIMARY KEY(value_id),
  FOREIGN KEY table_id REFERENCES ref_table_t (table_id) ON DELETE CASCADE
);


CREATE TABLE value_locale_t (
  value_id              VARCHAR(22) NOT NULL,
  language              VARCHAR(2) NOT NULL,
  value_desc            VARCHAR(256) NULL, -- The drop label in language.
  PRIMARY KEY(value_id,language),
  FOREIGN KEY value_id REFERENCES ref_value_t (value_id) ON DELETE CASCADE
);



CREATE TABLE relation_type_t (
  relation_id           VARCHAR(22) NOT NULL,
  relation_name         VARCHAR(32) NOT NULL, -- The lookup keyword for the relation.
  relation_desc         VARCHAR(1024) NOT NULL,
  PRIMARY KEY(relation_id)
);



CREATE TABLE relation_t (
  relation_id           VARCHAR(22) NOT NULL,
  value_id_from         VARCHAR(22) NOT NULL,
  value_id_to           VARCHAR(22) NOT NULL,
  active                VARCHAR(1) NOT NULL DEFAULT 'Y',
  PRIMARY KEY(relation_id, value_id_from, value_id_to)
  FOREIGN KEY relation_id REFERENCES relation_type_t (relation_id) ON DELETE CASCADE,
  FOREIGN KEY value_id_from REFERENCES ref_value_t (value_id) ON DELETE CASCADE,
  FOREIGN KEY value_id_to REFERENCES ref_table_t (value_id) ON DELETE CASCADE
);

```


