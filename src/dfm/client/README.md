# Data Federation Mesh Client (DFM)

Data Federation Mesh client allows for submitting processing pipelines
to a Data Federation Mesh (DFM) instance and gathering responses from that
DFM instance.

Thanks to familiar asynchronous context pattern, `AsyncClient` objects
can be used in a straightforward manner:

```python
pipeline = build_dfm_pipeline()

async with AsyncClient(url='http://localhost:8080') as client:
    # Submit a data processing pipeline to DFM
    request_id = await client.process(pipeline)
    # Wait for responses produced by the DFM and process
    async for result in client.responses(request_id):
        if not result:
            await asyncio.sleep(0.5)
            continue
        end = process_result(result)
        if end:
            break
```

The calling code must decide when it received all awaited responses and
stop polling for new ones. The `AsyncClient.responses()` method accepts
an optional argument that can be used to pass a list of awaited node IDs
to the client, which will end the iteration when all relevant responses are
collected.

For more information, please consult DFM documentation.
