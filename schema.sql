PRAGMA foreign_keys=ON;
-- access_role (added by the compatible startup migration) is the authorization role.
-- role remains a legacy column so existing foreign-key-linked user records need no rebuild.
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,username TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('MASTER','STAFF')),active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS properties(id INTEGER PRIMARY KEY,name TEXT NOT NULL,code TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sections(id INTEGER PRIMARY KEY,property_id INTEGER NOT NULL REFERENCES properties(id),name TEXT NOT NULL,active INTEGER DEFAULT 1,sort_order INTEGER DEFAULT 0,UNIQUE(property_id,name));
CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY,code TEXT UNIQUE,name TEXT NOT NULL,section_id INTEGER NOT NULL REFERENCES sections(id),specification TEXT NOT NULL DEFAULT '',category TEXT DEFAULT '',unit TEXT DEFAULT 'Nos',rate INTEGER,photo TEXT,active INTEGER DEFAULT 1,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS movements(id INTEGER PRIMARY KEY,item_id INTEGER NOT NULL REFERENCES items(id),section_id INTEGER NOT NULL REFERENCES sections(id),type TEXT NOT NULL,qty INTEGER NOT NULL,rate INTEGER,name TEXT NOT NULL,photo TEXT,reason TEXT,note TEXT,date TEXT NOT NULL,actor INTEGER NOT NULL REFERENCES users(id),request_id TEXT UNIQUE NOT NULL);
CREATE INDEX IF NOT EXISTS movements_item_date ON movements(item_id,date);
CREATE TABLE IF NOT EXISTS counts(id INTEGER PRIMARY KEY,section_id INTEGER NOT NULL REFERENCES sections(id),month TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'OPEN',UNIQUE(section_id,month));
CREATE TABLE IF NOT EXISTS lines(count_id INTEGER REFERENCES counts(id),item_id INTEGER REFERENCES items(id),actual INTEGER CHECK(actual>=0),note TEXT DEFAULT '',flag TEXT DEFAULT '',PRIMARY KEY(count_id,item_id));
CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY,count_id INTEGER NOT NULL REFERENCES counts(id),version INTEGER NOT NULL,data TEXT NOT NULL,created TEXT NOT NULL,UNIQUE(count_id,version));
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,actor INTEGER REFERENCES users(id),action TEXT NOT NULL,detail TEXT NOT NULL,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS archives(id INTEGER PRIMARY KEY,snapshot_id INTEGER REFERENCES snapshots(id),kind TEXT,format TEXT,path TEXT,sha256 TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS immutable_movement_update BEFORE UPDATE ON movements BEGIN SELECT RAISE(ABORT,'Ledger entries are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_movement_delete BEFORE DELETE ON movements BEGIN SELECT RAISE(ABORT,'Ledger entries are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_snapshot_update BEFORE UPDATE ON snapshots BEGIN SELECT RAISE(ABORT,'Snapshots are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_snapshot_delete BEFORE DELETE ON snapshots BEGIN SELECT RAISE(ABORT,'Snapshots are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_audit_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT,'Audit entries are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_audit_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT,'Audit entries are immutable'); END;

CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY,recipient_id INTEGER NOT NULL REFERENCES users(id),movement_id INTEGER NOT NULL REFERENCES movements(id),created TEXT NOT NULL,read_at TEXT,UNIQUE(recipient_id,movement_id));
CREATE INDEX IF NOT EXISTS notification_inbox ON notifications(recipient_id,read_at,id);

CREATE TABLE IF NOT EXISTS submissions(id INTEGER PRIMARY KEY,actor INTEGER NOT NULL REFERENCES users(id),section_id INTEGER NOT NULL REFERENCES sections(id),payload TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'PENDING',feedback TEXT NOT NULL DEFAULT '',revision INTEGER NOT NULL DEFAULT 1,reviewer INTEGER REFERENCES users(id),movement_id INTEGER REFERENCES movements(id),request_id TEXT UNIQUE NOT NULL,created TEXT NOT NULL,updated TEXT NOT NULL);

CREATE INDEX IF NOT EXISTS idx_items_section_active ON items(section_id, active);
CREATE INDEX IF NOT EXISTS idx_movements_section_date ON movements(section_id, date);
CREATE INDEX IF NOT EXISTS idx_counts_sec_month ON counts(section_id, month);
CREATE INDEX IF NOT EXISTS idx_lines_count_item ON lines(count_id, item_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_count ON snapshots(count_id, version);
CREATE INDEX IF NOT EXISTS idx_submissions_sec_status ON submissions(section_id, status);
