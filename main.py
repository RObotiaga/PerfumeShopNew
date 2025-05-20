# robotiaga-perfumeshopnew/main.py
import asyncio
import logging
from config import (
    GOOGLE_SHEET_URL,
    CREDENTIALS_JSON_PATH,
    LOGGING_CONFIG,
    QUEUE_WORKER_INTERVAL_SECONDS,
)
from app.database import AsyncSheetServiceWithQueue  # Import the new service
from typing import Dict, List, Any, Optional, Type

if LOGGING_CONFIG:
    import logging.config

    logging.config.dictConfig(LOGGING_CONFIG)
else:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
    )
logger = logging.getLogger(__name__)


async def run_demo(sheet_service: AsyncSheetServiceWithQueue):
    logger.info("\n--- RUNNING DEMO ---")
    await sheet_service._initial_gsheet_cache_populated.wait()  # Ensure initial GSheet fetch is done

    # --- Example: Read data from in-memory cache (populated from GSheet) ---
    logger.info("\n--- READING CACHED DATA (FROM GSHEET SOURCE) ---")
    products_data = await sheet_service.get_data_from_cache("Товары")
    if products_data:
        logger.info(
            f"Retrieved {len(products_data)} products from GSheet cache. First: {products_data[0] if products_data else 'None'}"
        )
    else:
        logger.info("No product data in GSheet cache for 'Товары'.")

    # --- Example: Create a new row (queues to SQLite, optimistically updates in-memory cache) ---
    logger.info(
        "\n--- CREATING NEW PRODUCT (QUEUED TO SQLITE, OPTIMISTIC CACHE UPDATE) ---"
    )
    test_product_id_queued = 99925  # New ID for this test run

    # Optional: Clean up previous test entry if any using direct GSheet delete (not through queue for cleanup)
    # For actual ops, use the queued methods.
    # await sheet_service.delete_rows("Товары", filter_criteria={"product_id": test_product_id_queued}) # This would queue delete
    # logger.info(f"Attempted pre-cleanup for product ID {test_product_id_queued} (queued).")
    # await asyncio.sleep(QUEUE_WORKER_INTERVAL_SECONDS + 5) # Wait for worker to potentially process it

    new_product_payload_q = {
        "product_id": test_product_id_queued,
        "product_name": "Queued Test Product",
        "category": "Queued Category",
        "price_per_unit": 25.25,
        "status": "Active Queued",
    }
    created_product_optimistic = await sheet_service.create_row(
        "Товары", new_product_payload_q
    )
    if created_product_optimistic:
        logger.info(
            f"Create operation queued. Optimistic data: {created_product_optimistic}"
        )

        # Check in-memory cache (should reflect optimistic update)
        cached_after_optimistic_create = await sheet_service.read_rows_from_cache(
            "Товары", filter_criteria={"product_id": test_product_id_queued}
        )
        logger.info(
            f"Product in IN-MEMORY CACHE (optimistic) after create: {cached_after_optimistic_create[0] if cached_after_optimistic_create else 'Not found optimistically'}"
        )
    else:
        logger.error("Failed to queue create operation.")

    logger.info(
        f"--- WAITING FOR QUEUE WORKER TO PROCESS (approx {QUEUE_WORKER_INTERVAL_SECONDS}s + GSheet API time) ---"
    )
    # In a real app, you wouldn't typically block like this.
    # The worker runs in the background. This is just for demo to see GSheet effect.
    await asyncio.sleep(
        QUEUE_WORKER_INTERVAL_SECONDS + 15
    )  # Wait longer than worker interval + some processing time

    # --- Force GSheet cache refresh and check if item is now in GSheet-sourced cache ---
    logger.info("\n--- FORCING GSHEET CACHE REFRESH TO VERIFY GSHEET WRITE ---")
    await sheet_service.force_gsheet_in_memory_cache_refresh("Товары")
    gsheet_sourced_product = await sheet_service.read_rows_from_cache(
        "Товары", filter_criteria={"product_id": test_product_id_queued}
    )
    if gsheet_sourced_product:
        logger.info(
            f"Product (ID: {test_product_id_queued}) found in GSheet-sourced cache after worker processing: {gsheet_sourced_product[0]}"
        )
    else:
        logger.warning(
            f"Product (ID: {test_product_id_queued}) NOT found in GSheet-sourced cache. Worker might not have finished or GSheet write failed."
        )

    # --- Example: Update (queues, optimistic update) ---
    if gsheet_sourced_product:  # Only if create was likely successful in GSheet
        logger.info(
            f"\n--- UPDATING PRODUCT (ID: {test_product_id_queued}) (QUEUED, OPTIMISTIC) ---"
        )
        update_payload_q = {"status": "Updated via Queue", "price_per_unit": 28.82}
        update_queued_ack = await sheet_service.update_rows(
            "Товары",
            filter_criteria={"product_id": test_product_id_queued},
            new_data_payload=update_payload_q,
        )
        if update_queued_ack:
            logger.info(
                f"Update operation queued for product ID {test_product_id_queued}."
            )
            cached_after_optimistic_update = await sheet_service.read_rows_from_cache(
                "Товары", filter_criteria={"product_id": test_product_id_queued}
            )
            logger.info(
                f"Product in IN-MEMORY CACHE (optimistic) after update: {cached_after_optimistic_update[0] if cached_after_optimistic_update else 'Not found optimistically'}"
            )

            logger.info(f"--- WAITING FOR QUEUE WORKER FOR UPDATE ---")
            await asyncio.sleep(QUEUE_WORKER_INTERVAL_SECONDS + 10)
            await sheet_service.force_gsheet_in_memory_cache_refresh("Товары")
            gsheet_updated_product = await sheet_service.read_rows_from_cache(
                "Товары", filter_criteria={"product_id": test_product_id_queued}
            )
            logger.info(
                f"Product (ID: {test_product_id_queued}) in GSheet-sourced cache after update worker: {gsheet_updated_product[0] if gsheet_updated_product else 'Not found'}"
            )

    # --- Example: Delete (queues, optimistic update) ---
    # Always try to clean up to make test rerunnable
    logger.info(
        f"\n--- DELETING PRODUCT (ID: {test_product_id_queued}) (QUEUED, OPTIMISTIC) ---"
    )
    delete_queued_ack = await sheet_service.delete_rows(
        "Товары", filter_criteria={"product_id": test_product_id_queued}
    )
    if delete_queued_ack:
        logger.info(f"Delete operation queued for product ID {test_product_id_queued}.")
        cached_after_optimistic_delete = await sheet_service.read_rows_from_cache(
            "Товары", filter_criteria={"product_id": test_product_id_queued}
        )  # Should be empty
        logger.info(
            f"Product in IN-MEMORY CACHE (optimistic) after delete: {'Not found (correct)' if not cached_after_optimistic_delete else cached_after_optimistic_delete}"
        )

        logger.info(f"--- WAITING FOR QUEUE WORKER FOR DELETE ---")
        await asyncio.sleep(QUEUE_WORKER_INTERVAL_SECONDS + 10)
        await sheet_service.force_gsheet_in_memory_cache_refresh("Товары")
        gsheet_deleted_product = await sheet_service.read_rows_from_cache(
            "Товары", filter_criteria={"product_id": test_product_id_queued}
        )
        logger.info(
            f"Product (ID: {test_product_id_queued}) in GSheet-sourced cache after delete worker: {'Not found (correct)' if not gsheet_deleted_product else gsheet_deleted_product}"
        )


async def main_async_entry():
    logger.info("Starting Asynchronous Sheet Service Application...")
    sheet_service_instance = None
    try:
        sheet_service_instance = AsyncSheetServiceWithQueue(
            sheet_url=GOOGLE_SHEET_URL, credentials_path=CREDENTIALS_JSON_PATH
        )
        await sheet_service_instance.start_services()
        logger.info("Sheet service initialized and background tasks started.")

        await run_demo(sheet_service_instance)

    except FileNotFoundError as e:
        logger.error(f"Configuration error: {e}")
    except ValueError as e:
        logger.error(f"Initialization error: {e}")
    except Exception as e:
        logger.error(f"An unexpected error in main_async_entry: {e}", exc_info=True)
    finally:
        if sheet_service_instance:
            logger.info("Shutting down sheet service...")
            await sheet_service_instance.close()
        logger.info("Application finished.")


if __name__ == "__main__":
    try:
        asyncio.run(main_async_entry())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user.")
    except Exception as e:
        logger.critical(f"Critical error during asyncio.run: {e}", exc_info=True)
