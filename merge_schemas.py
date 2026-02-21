import os

def merge_schemas():
    schema_path = 'schema.sql'
    fixes_path = 'schema_fixes.sql'
    dev_path = 'schema_rls_dev.sql'
    prod_path = 'schema_rls_prod.sql'
    
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema = f.read()

    with open(prod_path, 'r', encoding='utf-8') as f:
        prod_rls = f.read()

    # Apply fixes from schema_fixes.sql
    schema = schema.replace('VECTOR(768)', 'VECTOR(3072)')
    schema = schema.replace('vector(768)', 'vector(3072)')
    schema = schema.replace('lists = 100', 'lists = 50')

    # Extract prod RLS policies (skip the first few lines of comments)
    prod_lines = prod_rls.split('\n')
    prod_content = '\n'.join([line for line in prod_lines if not line.startswith('-- Menu Green - Production')])
    
    # Append the PROD RLS to the schema before the triggers, or at the end.
    # It's perfectly fine to append it to the end of the file.
    
    # Actually, schema.sql has a TRIGGER section at the bottom. 
    # Let's cleanly inject the PROD RLS just before the TRIGGERS section so it stays organized.
    trigger_marker = '-- =====================================================\n-- TRIGGERS FOR AUTOMATIC UPDATED_AT\n-- ====================================================='
    
    if trigger_marker in schema:
        parts = schema.split(trigger_marker)
        schema = parts[0] + "\n" + prod_content + "\n\n" + trigger_marker + parts[1]
    else:
        schema += "\n\n" + prod_content

    with open(schema_path, 'w', encoding='utf-8') as f:
        f.write(schema)

    # Delete the redundant files
    if os.path.exists(fixes_path): os.remove(fixes_path)
    if os.path.exists(dev_path): os.remove(dev_path)
    if os.path.exists(prod_path): os.remove(prod_path)
    
    print("Merge complete!")

if __name__ == '__main__':
    merge_schemas()
