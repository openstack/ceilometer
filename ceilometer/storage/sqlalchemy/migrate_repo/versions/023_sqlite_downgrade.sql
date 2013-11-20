ALTER TABLE trait RENAME TO trait_orig;

INSERT INTO unique_name
SELECT id, 'desc'
FROM trait_type;

CREATE TABLE trait (
  id INTEGER PRIMARY KEY ASC,
  t_string VARCHAR(255),
  t_int INTEGER,
  t_float FLOAT,
  t_datetime FLOAT,
  t_type INTEGER NOT NULL,
  name_id INTEGER NOT NULL,
  event_id INTEGER NOT NULL,
  FOREIGN KEY (name_id) REFERENCES unique_name (id)
  FOREIGN KEY (event_id) REFERENCES event (id)
);


INSERT INTO trait
SELECT t.id, t.t_string, t.t_int, t.t_float, t.t_datetime
    tt.data_type, t.trait_type_id, t.event_id
FROM trait_orig t
INNER JOIN trait_type tt
ON tt.id = t.trait_type_id

DROP TABLE trait_orig;
DROP TABLE trait_type;
