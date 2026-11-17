import psycopg
from app import config

def seed():
    with psycopg.connect(config.ADMIN_DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                GRANT ALL ON ALL TABLES IN SCHEMA public TO cm_app;
                GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO cm_app;
            """)
            conn.commit()

            cur.execute("SELECT case_id FROM cases WHERE case_ref = 'CASE-2026-001'")
            row = cur.fetchone()
            if row:
                case_id = row[0]
                cameras = [
                    ('CAM-01', 'East Perimeter Gate Alpha', '1920x1080', 30.0, 'Green Park East Gate Outer Perimeter'),
                    ('CAM-02', 'North Walkway PTZ', '1920x1080', 30.0, 'Green Park North Avenue Corridor'),
                    ('CAM-05', 'Central Gazebo Dome Optic', '1920x1080', 30.0, 'Central Gazebo Lawn Primary Scene'),
                    ('CAM-L-P01', 'South Parking Lot Entry Barrier', '2560x1440', 25.0, 'Visitor Parking South Gate'),
                ]
                for ref, name, res, fps, zone in cameras:
                    cur.execute("""
                        INSERT INTO cctv_cameras (case_id, ref, name, resolution, fps, coverage_zone)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (case_id, ref) DO UPDATE SET
                            name = EXCLUDED.name,
                            coverage_zone = EXCLUDED.coverage_zone
                    """, (case_id, ref, name, res, fps, zone))
                conn.commit()
                print("CAMERAS SEEDED SUCCESSFULLY!")

if __name__ == "__main__":
    seed()
