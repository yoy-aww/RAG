CREATE USER IF NOT EXISTS 'rag_ro'@'%' IDENTIFIED BY 'ro123';
CREATE USER IF NOT EXISTS 'rag_ro'@'localhost' IDENTIFIED BY 'ro123';
GRANT SELECT ON yoyac_pv.* TO 'rag_ro'@'%';
GRANT SELECT ON yoyac_pv.* TO 'rag_ro'@'localhost';
FLUSH PRIVILEGES;
SHOW GRANTS FOR 'rag_ro'@'%';
SHOW GRANTS FOR 'rag_ro'@'localhost';
