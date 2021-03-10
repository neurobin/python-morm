
import morm

class MigrationRunner(morm.migration.MigrationRunner):
    """Run migration with pre and after steps.
    """
    migration_query = """DROP TABLE "SiteUser";CREATE TABLE "SiteUser" (
    "id" SERIAL NOT NULL,
    "name" varchar(255) ,
    "profession" varchar(255) ,
    "age" integer
);


"""

    async def run_before(self):
        """Run before migration

        self.tdb is the db handle (transaction)
        self.model is the model class
        """
        dbm = self.tdb(self.model)
        # # Example
        # dbm.q('SOME QUERY TO SET "column_1"=$1', 'some_value')
        # await dbm.execute()
        # # etc..

    async def run_after(self):
        """Run after migration.

        self.tdb is the db handle (transaction)
        self.model is the model class
        """
        dbm = self.tdb(self.model)
        # # Example
        # dbm.q('SOME QUERY TO SET "column_1"=$1', 'some_value')
        # await dbm.execute()
        # # etc..
