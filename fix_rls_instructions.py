"""
Fix Row Level Security issue for recipes table.

The database has RLS enabled but no policies are configured yet.
This script provides SQL commands to fix it.
"""

print("""
🔒 Row Level Security (RLS) Issue Detected
==========================================

Vấn đề: Table 'recipes' có RLS enabled nhưng chưa có policies.
Mọi insert/update/delete operation đều bị chặn.

🔧 Cách sửa:
-----------

Bước 1: Đăng nhập vào Supabase Dashboard
  → https://supabase.com/dashboard

Bước 2: Chọn project của bạn

Bước 3: Vào SQL Editor (biểu tượng⚡ trong sidebar)

Bước 4: Copy và chạy SQL sau:

```sql
-- Disable RLS temporarily for development
ALTER TABLE recipes DISABLE ROW LEVEL SECURITY;

-- If you want to keep RLS enabled, use these policies instead:
-- ALTER TABLE recipes ENABLE ROW LEVEL SECURITY;
-- 
-- CREATE POLICY "Enable read access for all users" ON recipes
--     FOR SELECT USING (true);
-- 
-- CREATE POLICY "Enable insert for all users" ON recipes
--     FOR INSERT WITH CHECK (true);
-- 
-- CREATE POLICY "Enable update for all users" ON recipes
--     FOR UPDATE USING (true);
-- 
-- CREATE POLICY "Enable delete for all users" ON recipes
--     FOR DELETE USING (true);
```

Bước 5: Sau khi chạy SQL, quay lại terminal và chạy lại:
  python quick_ingest.py

📌 Lưu ý:
---------
- Disable RLS chỉ nên dùng cho development/testing
- Trong production, cần cấu hình RLS policies đúng cách
- File 'fix_rls.sql' có các policies mẫu bạn có thể sử dụng

""")
