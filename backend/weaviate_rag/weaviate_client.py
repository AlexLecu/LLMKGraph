"""Single place that decides how to connect to Weaviate, driven by env vars.

- WEAVIATE_URL + WEAVIATE_API_KEY  -> Weaviate Cloud
- WEAVIATE_MODE=embedded           -> in-process Weaviate (Linux), data in WEAVIATE_DATA_PATH
- WEAVIATE_HOST / WEAVIATE_HTTP_PORT / WEAVIATE_GRPC_PORT -> a running server
  (defaults: localhost / 8080 / 50051)
"""
import os

import weaviate


def get_weaviate_client():
    cloud_url = os.getenv('WEAVIATE_URL')
    if cloud_url:
        from weaviate.classes.init import Auth
        return weaviate.connect_to_weaviate_cloud(
            cluster_url=cloud_url,
            auth_credentials=Auth.api_key(os.environ['WEAVIATE_API_KEY']),
        )

    if os.getenv('WEAVIATE_MODE', '').lower() == 'embedded':
        return weaviate.connect_to_embedded(
            persistence_data_path=os.getenv('WEAVIATE_DATA_PATH', './weaviate_data'),
        )

    host = os.getenv('WEAVIATE_HOST', 'localhost')
    http_port = int(os.getenv('WEAVIATE_HTTP_PORT', '8080'))
    grpc_port = int(os.getenv('WEAVIATE_GRPC_PORT', '50051'))
    if host == 'localhost':
        return weaviate.connect_to_local(port=http_port, grpc_port=grpc_port)
    return weaviate.connect_to_custom(
        http_host=host, http_port=http_port, http_secure=False,
        grpc_host=host, grpc_port=grpc_port, grpc_secure=False,
    )
