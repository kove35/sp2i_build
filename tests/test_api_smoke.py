"""
Smoke tests du projet SP2I_Build.

Ces tests couvrent les flux critiques sans toucher durablement
aux donnees metier :

- endpoints dashboard
- CRUD DQE
- CRUD analytique SQLAlchemy
- endpoint de reseed analytique
"""

from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.db.session import SessionLocal
from backend.main import app
from backend.models.build_analytics import BuildArticle, BuildFactMetre, BuildProject


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQLITE_SOURCE_DB = PROJECT_ROOT / "sp2i_build.db"


class APISmokeTests(unittest.TestCase):
    """
    Suite de smoke tests pour les API principales.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def tearDown(self) -> None:
        """
        Nettoie les donnees temporaires creees par les tests.
        """
        self._cleanup_dqe_articles()
        self._cleanup_analytics_facts()
        self._cleanup_test_projects()

    def _cleanup_dqe_articles(self) -> None:
        with sqlite3.connect(SQLITE_SOURCE_DB) as connection:
            connection.execute(
                "DELETE FROM articles_dqe WHERE designation LIKE ?",
                ("TEST_SMOKE_%",),
            )
            connection.commit()

    def _cleanup_analytics_facts(self) -> None:
        session = SessionLocal()
        try:
            session.query(BuildFactMetre).filter(
                BuildFactMetre.source_row_key.like("TEST_SMOKE_%")
            ).delete(synchronize_session=False)
            session.commit()
        finally:
            session.close()

    def _cleanup_test_projects(self) -> None:
        session = SessionLocal()
        try:
            projects = (
                session.query(BuildProject)
                .filter(
                    (BuildProject.code.like("TEST_PDF_PROMO_%"))
                    | (BuildProject.code.like("TEST_INTEL_DQE_%"))
                )
                .all()
            )
            for project in projects:
                session.delete(project)
            session.commit()
        finally:
            session.close()

    def _get_first_project(self) -> dict:
        response = self.client.get("/analytics/projects")
        self.assertEqual(response.status_code, 200)
        projects = response.json()
        self.assertTrue(projects)
        return projects[0]

    def _get_seed_reference(self) -> dict:
        session = SessionLocal()
        try:
            project = session.query(BuildProject).order_by(BuildProject.id.asc()).first()
            self.assertIsNotNone(project)

            article = (
                session.query(BuildArticle)
                .filter(BuildArticle.project_id == project.id)
                .order_by(BuildArticle.id.asc())
                .first()
            )
            self.assertIsNotNone(article)

            return {
                "project_id": project.id,
                "code_bpu": article.code_bpu,
                "lot_code": article.lot.code if article.lot else None,
                "famille_code": article.famille.code if article.famille else None,
            }
        finally:
            session.close()

    def test_root_and_dashboard_endpoints(self) -> None:
        root_response = self.client.get("/")
        self.assertEqual(root_response.status_code, 200)
        root_payload = root_response.json()
        self.assertEqual(root_payload["status"], "ok")

        filters_response = self.client.get("/filters")
        self.assertEqual(filters_response.status_code, 200)
        filters_payload = filters_response.json()
        self.assertIn("lots", filters_payload)
        self.assertTrue(filters_payload["lots"])

        direction_response = self.client.get("/kpi_direction")
        self.assertEqual(direction_response.status_code, 200)
        direction_payload = direction_response.json()
        self.assertIn("kpis", direction_payload)
        self.assertIn("charts", direction_payload)

        chantier_response = self.client.get("/kpi_chantier")
        self.assertEqual(chantier_response.status_code, 200)
        self.assertIn("kpis", chantier_response.json())

        import_response = self.client.get("/kpi_import")
        self.assertEqual(import_response.status_code, 200)
        self.assertIn("kpis", import_response.json())

        direction_dataset_response = self.client.get("/direction_dataset")
        self.assertEqual(direction_dataset_response.status_code, 200)
        dataset_payload = direction_dataset_response.json()
        self.assertIn("items", dataset_payload)
        self.assertGreater(len(dataset_payload["items"]), 0)

    def test_dqe_crud_flow(self) -> None:
        payload = {
            "lot": "TEST LOT",
            "sous_lot": "TEST FAMILLE",
            "designation": f"TEST_SMOKE_DQE_{uuid4().hex[:8]}",
            "unite": "M2",
            "quantite": 12,
            "pu_local": 1000,
            "pu_chine": 800,
        }

        create_response = self.client.post("/article", json=payload)
        self.assertEqual(create_response.status_code, 200)
        created_article = create_response.json()
        self.assertEqual(created_article["total_local"], 12000)
        self.assertEqual(created_article["total_import"], 9600)

        article_id = created_article["id"]

        list_response = self.client.get("/articles", params={"lot": "TEST LOT"})
        self.assertEqual(list_response.status_code, 200)
        list_payload = list_response.json()
        self.assertTrue(
            any(item["id"] == article_id for item in list_payload["items"])
        )

        update_payload = {
            **payload,
            "quantite": 15,
            "pu_local": 1100,
            "pu_chine": 900,
        }
        update_response = self.client.put(f"/article/{article_id}", json=update_payload)
        self.assertEqual(update_response.status_code, 200)
        updated_article = update_response.json()
        self.assertEqual(updated_article["total_local"], 16500)
        self.assertEqual(updated_article["total_import"], 13500)

        delete_response = self.client.delete(f"/article/{article_id}")
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()["status"], "deleted")

    def test_analytics_dashboard_and_filters(self) -> None:
        project = self._get_first_project()
        project_id = project["id"]

        filters_response = self.client.get(f"/analytics/projects/{project_id}/filters")
        self.assertEqual(filters_response.status_code, 200)
        filters_payload = filters_response.json()
        self.assertIn("lots", filters_payload)
        self.assertIn("familles", filters_payload)

        facts_response = self.client.get(f"/analytics/projects/{project_id}/facts")
        self.assertEqual(facts_response.status_code, 200)
        facts_payload = facts_response.json()
        self.assertIn("items", facts_payload)
        self.assertGreater(len(facts_payload["items"]), 0)

        dashboard_response = self.client.get(f"/analytics/projects/{project_id}/dashboard")
        self.assertEqual(dashboard_response.status_code, 200)
        dashboard_payload = dashboard_response.json()
        self.assertIn("kpis", dashboard_payload)
        self.assertIn("charts", dashboard_payload)

    def test_analytics_fact_crud_flow(self) -> None:
        reference = self._get_seed_reference()
        source_row_key = f"TEST_SMOKE_FACT_{uuid4().hex}"

        payload = {
            "code_bpu": reference["code_bpu"],
            "lot_code": reference["lot_code"],
            "famille_code": reference["famille_code"],
            "quantite": 2,
            "pu_local": 10000,
            "pu_chine": 7000,
            "decision": "IMPORT",
            "source_row_key": source_row_key,
        }

        create_response = self.client.post(
            f"/analytics/projects/{reference['project_id']}/facts",
            json=payload,
        )
        self.assertEqual(create_response.status_code, 200)
        created_fact = create_response.json()
        self.assertEqual(created_fact["decision"], "IMPORT")
        self.assertEqual(created_fact["total_local"], 20000.0)
        self.assertEqual(created_fact["total_import"], 14000.0)
        self.assertEqual(created_fact["economie"], 6000.0)

        fact_id = created_fact["id"]

        update_payload = {
            **payload,
            "quantite": 3,
            "pu_local": 12000,
            "pu_chine": 9000,
            "decision": "LOCAL",
        }
        update_response = self.client.put(
            f"/analytics/facts/{fact_id}",
            json=update_payload,
        )
        self.assertEqual(update_response.status_code, 200)
        updated_fact = update_response.json()
        self.assertEqual(updated_fact["decision"], "LOCAL")
        self.assertEqual(updated_fact["total_local"], 36000.0)
        self.assertEqual(updated_fact["total_import"], 27000.0)
        self.assertEqual(updated_fact["economie"], 0.0)

        delete_response = self.client.delete(f"/analytics/facts/{fact_id}")
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()["status"], "deleted")

    def test_analytics_reseed_endpoint(self) -> None:
        reseed_response = self.client.post("/analytics/reseed")
        self.assertEqual(reseed_response.status_code, 200)
        reseed_payload = reseed_response.json()
        self.assertEqual(reseed_payload["project_code"], "PNR_MEDICAL_CENTER")
        self.assertGreater(reseed_payload["fact_rows"], 0)

    def test_dqe_pdf_control_endpoints(self) -> None:
        summary_response = self.client.get("/analytics/dqe/summary")
        self.assertEqual(summary_response.status_code, 200)
        summary_payload = summary_response.json()
        self.assertTrue(summary_payload["pdf_exists"])
        self.assertGreater(summary_payload["lots_imported"], 0)

        lot_response = self.client.get("/analytics/dqe/lot-comparison")
        self.assertEqual(lot_response.status_code, 200)
        lot_payload = lot_response.json()
        self.assertIn("items", lot_payload)
        self.assertGreater(len(lot_payload["items"]), 0)

        article_response = self.client.get(
            "/analytics/dqe/article-comparison",
            params={"lot_code": "LOT 1"},
        )
        self.assertEqual(article_response.status_code, 200)
        article_payload = article_response.json()
        self.assertIn("items", article_payload)

    def test_dqe_pdf_promote_endpoint(self) -> None:
        source_files_response = self.client.get("/analytics/dqe/source-files")
        self.assertEqual(source_files_response.status_code, 200)
        source_files_payload = source_files_response.json()
        self.assertTrue(source_files_payload["items"])

        test_project_code = f"TEST_PDF_PROMO_{uuid4().hex[:8].upper()}"
        promote_response = self.client.post(
            "/analytics/dqe/promote",
            json={
                "source_file": source_files_payload["items"][0],
                "project_code": test_project_code,
                "project_name": f"Test PDF Promote {test_project_code}",
                "replace_existing": False,
            },
        )
        self.assertEqual(promote_response.status_code, 200)
        promote_payload = promote_response.json()
        self.assertEqual(promote_payload["project_code"], test_project_code)
        self.assertGreater(promote_payload["fact_rows"], 0)

    def test_smart_dqe_import_flow(self) -> None:
        csv_content = (
            "Batiment,Niveau,Lot,Sous Lot,Designation,Unite,Quantite,PU Local,PU Chine\n"
            "Principal,RDC,Electricite,Prises,Prise 2P+T,U,10,12000,9000\n"
            "Annexe,R+1,Plomberie,Tuyaux,Tuyau PVC D50,ML,25,3500,2500\n"
        )

        with NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            prefix="test_intelligent_dqe_",
            dir=PROJECT_ROOT,
            delete=False,
            encoding="utf-8",
        ) as handle:
            handle.write(csv_content)
            csv_path = Path(handle.name)

        try:
            preview_response = self.client.post(
                "/analytics/dqe-smart/preview",
                json={"file_path": str(csv_path)},
            )
            self.assertEqual(preview_response.status_code, 200)
            preview_payload = preview_response.json()
            self.assertEqual(preview_payload["row_count_standardized"], 2)

            project_code = f"TEST_INTEL_DQE_{uuid4().hex[:8].upper()}"
            create_project_response = self.client.post(
                "/analytics/projects",
                json={
                    "code": project_code,
                    "name": f"Test intelligent {project_code}",
                    "description": "Projet de test import intelligent",
                    "devise": "FCFA",
                    "statut": "draft",
                },
            )
            self.assertEqual(create_project_response.status_code, 200)
            project_payload = create_project_response.json()

            set_default_response = self.client.post(
                f"/analytics/default-project/{project_payload['id']}"
            )
            self.assertEqual(set_default_response.status_code, 200)

            default_response = self.client.get("/analytics/default-project")
            self.assertEqual(default_response.status_code, 200)
            self.assertEqual(default_response.json()["project"]["id"], project_payload["id"])

            import_response = self.client.post(
                "/analytics/dqe-smart/import",
                json={
                    "project_id": project_payload["id"],
                    "file_path": str(csv_path),
                    "replace_existing": True,
                },
            )
            self.assertEqual(import_response.status_code, 200)
            import_payload = import_response.json()
            self.assertEqual(import_payload["imported_rows"], 2)

            hierarchy_response = self.client.get(
                f"/analytics/projects/{project_payload['id']}/hierarchy-items"
            )
            self.assertEqual(hierarchy_response.status_code, 200)
            hierarchy_payload = hierarchy_response.json()
            self.assertEqual(len(hierarchy_payload["items"]), 2)
        finally:
            if csv_path.exists():
                csv_path.unlink()


if __name__ == "__main__":
    unittest.main(verbosity=2)
