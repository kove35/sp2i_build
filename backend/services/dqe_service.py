"""
Service CRUD pour la saisie DQE.
"""

from __future__ import annotations

from backend.database import get_connection
from backend.schemas import DQEArticlePayload


class DQEArticleService:
    """
    Gere les articles DQE dans SQLite.
    """

    def create_article(self, payload: DQEArticlePayload) -> dict:
        """
        Cree un article avec calcul automatique des totaux.
        """
        total_local = payload.quantite * payload.pu_local
        total_import = payload.quantite * payload.pu_chine

        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO articles_dqe (
                    lot,
                    sous_lot,
                    designation,
                    unite,
                    quantite,
                    pu_local,
                    pu_chine,
                    total_local,
                    total_import
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.lot,
                    payload.sous_lot,
                    payload.designation,
                    payload.unite,
                    payload.quantite,
                    payload.pu_local,
                    payload.pu_chine,
                    total_local,
                    total_import,
                ),
            )
            connection.commit()
            article_id = cursor.lastrowid

        return self.get_article_by_id(article_id)

    def update_article(self, article_id: int, payload: DQEArticlePayload) -> dict:
        """
        Met a jour un article existant.
        """
        total_local = payload.quantite * payload.pu_local
        total_import = payload.quantite * payload.pu_chine

        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE articles_dqe
                SET
                    lot = ?,
                    sous_lot = ?,
                    designation = ?,
                    unite = ?,
                    quantite = ?,
                    pu_local = ?,
                    pu_chine = ?,
                    total_local = ?,
                    total_import = ?
                WHERE id = ?
                """,
                (
                    payload.lot,
                    payload.sous_lot,
                    payload.designation,
                    payload.unite,
                    payload.quantite,
                    payload.pu_local,
                    payload.pu_chine,
                    total_local,
                    total_import,
                    article_id,
                ),
            )
            connection.commit()

            if cursor.rowcount == 0:
                raise ValueError("Article introuvable.")

        return self.get_article_by_id(article_id)

    def delete_article(self, article_id: int) -> None:
        """
        Supprime un article.
        """
        with get_connection() as connection:
            cursor = connection.execute(
                "DELETE FROM articles_dqe WHERE id = ?",
                (article_id,),
            )
            connection.commit()

            if cursor.rowcount == 0:
                raise ValueError("Article introuvable.")

    def get_article_by_id(self, article_id: int) -> dict:
        """
        Retourne un article a partir de son identifiant.
        """
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM articles_dqe WHERE id = ?",
                (article_id,),
            ).fetchone()

        if row is None:
            raise ValueError("Article introuvable.")

        return dict(row)

    def list_articles(
        self,
        lot: str | None = None,
        sous_lot: str | None = None,
    ) -> dict:
        """
        Retourne la liste des articles avec filtres facultatifs.
        """
        conditions: list[str] = []
        query_params: dict[str, str] = {}

        if lot:
            conditions.append("lot = :lot")
            query_params["lot"] = lot

        if sous_lot:
            conditions.append("sous_lot = :sous_lot")
            query_params["sous_lot"] = sous_lot

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        with get_connection() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM articles_dqe
                {where_clause}
                ORDER BY lot, sous_lot, designation
                """,
                query_params,
            ).fetchall()

            lot_rows = connection.execute(
                """
                SELECT DISTINCT lot
                FROM articles_dqe
                WHERE lot IS NOT NULL AND lot <> ''
                ORDER BY lot
                """
            ).fetchall()
            sous_lot_rows = connection.execute(
                """
                SELECT DISTINCT sous_lot
                FROM articles_dqe
                WHERE sous_lot IS NOT NULL AND sous_lot <> ''
                ORDER BY sous_lot
                """
            ).fetchall()

        return {
            "items": [dict(row) for row in rows],
            "filters": {
                "lots": [row["lot"] for row in lot_rows],
                "familles": [row["sous_lot"] for row in sous_lot_rows],
            },
        }
