-- 强制重置密码
SET PASSWORD FOR 'rag_ro'@'%' = 'ro123';
SET PASSWORD FOR 'rag_ro'@'localhost' = 'ro123';

-- 或者用 ALTER USER (MySQL 8.0+)
ALTER USER 'rag_ro'@'%' IDENTIFIED BY 'ro123';
ALTER USER 'rag_ro'@'localhost' IDENTIFIED BY 'ro123';

FLUSH PRIVILEGES;

-- 确认密码 hash 已更新（非空）
SELECT User, Host, Password FROM mysql.user WHERE User='rag_ro';
