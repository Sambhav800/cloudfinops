"""
Automated billing ingestion helpers for read-only bucket/dataset sync.
"""

from __future__ import annotations

import io
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class BillingIngestor:
    """
    Pull billing exports from provider storage using read-only credentials.
    """

    @staticmethod
    def pull_aws_cur(
        bucket_name: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
    ) -> Optional[bytes]:
        try:
            import boto3

            s3 = boto3.client(
                "s3",
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
            )
            response = s3.list_objects_v2(Bucket=bucket_name)
            contents = response.get("Contents", [])
            if not contents:
                return None

            latest = sorted(contents, key=lambda item: item.get("LastModified"), reverse=True)[0]
            object_key = latest.get("Key")
            if not object_key:
                return None

            payload = s3.get_object(Bucket=bucket_name, Key=object_key)
            body = payload.get("Body")
            if body is None:
                return None
            return body.read()
        except Exception as error:
            logger.error("Failed to pull AWS CUR from %s: %s", bucket_name, error)
            return None

    @staticmethod
    def pull_azure_cost_export(container_name: str, connection_string: str) -> Optional[bytes]:
        try:
            from azure.storage.blob import BlobServiceClient

            blob_service = BlobServiceClient.from_connection_string(connection_string)
            container = blob_service.get_container_client(container_name)
            blobs = list(container.list_blobs())
            if not blobs:
                return None

            latest = sorted(blobs, key=lambda item: item.last_modified, reverse=True)[0]
            blob_client = blob_service.get_blob_client(container=container_name, blob=latest.name)
            return blob_client.download_blob().readall()
        except Exception as error:
            logger.error("Failed to pull Azure billing export from %s: %s", container_name, error)
            return None

    @staticmethod
    def pull_gcp_billing_export(dataset_id: str, credentials_json: str) -> Optional[bytes]:
        """
        dataset_id must be in `project.dataset.table` format.
        """
        try:
            from google.cloud import bigquery
            from google.oauth2 import service_account

            credentials_info = json.loads(credentials_json)
            credentials = service_account.Credentials.from_service_account_info(credentials_info)
            client = bigquery.Client(credentials=credentials, project=credentials.project_id)

            query = (
                "SELECT * "
                f"FROM `{dataset_id}` "
                "WHERE usage_start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)"
            )

            result = client.query(query).result()
            rows = [dict(row.items()) for row in result]
            if not rows:
                return None

            import pandas as pd

            frame = pd.DataFrame(rows)
            buffer = io.StringIO()
            frame.to_csv(buffer, index=False)
            return buffer.getvalue().encode("utf-8")
        except Exception as error:
            logger.error("Failed to pull GCP billing export from %s: %s", dataset_id, error)
            return None
