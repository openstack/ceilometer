ALTER TABLE trait RENAME TO trait_orig;

CREATE TABLE trait_type (
  id INTEGER PRIMARY KEY ASC,
  'desc' STRING NOT NULL,
  data_type INTEGER NOT NULL,
  UNIQUE ('desc', data_type)
);

INSERT INTO trait_type
SELECT un.id, un.key, t.t_type
FROM unique_name un
JOIN trait_orig t ON un.id = t.name_id
GROUP BY un.id;

CREATE TABLE trait (
  id INTEGER PRIMARY KEY ASC,
  t_string VARCHAR(255),
  t_int INTEGER,
  t_float FLOAT,
  t_datetime FLOAT,
  trait_type_id INTEGER NOT NULL,
  event_id INTEGER NOT NULL,
  FOREIGN KEY (trait_type_id) REFERENCES trait_type (id)
  FOREIGN KEY (event_id) REFERENCES event (id)
);

INSERT INTO trait
SELECT t.id, t.t_string, t.t_int, t.t_float, t.t_datetime, t.name_id,
    t.event_id
FROM trait_orig t;

DROP TABLE trait_orig;
DROP TABLE unique_name;