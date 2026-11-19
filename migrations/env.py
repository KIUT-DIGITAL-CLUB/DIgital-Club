import logging
from logging.config import fileConfig

import sqlalchemy as sa
from flask import current_app

from alembic import context
from alembic.script import ScriptDirectory

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')


def get_engine():
    try:
        # this works with Flask-SQLAlchemy<3 and Alchemical
        return current_app.extensions['migrate'].db.get_engine()
    except (TypeError, AttributeError):
        # this works with Flask-SQLAlchemy>=3
        return current_app.extensions['migrate'].db.engine


def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace(
            '%', '%%')
    except AttributeError:
        return str(get_engine().url).replace('%', '%%')


# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
config.set_main_option('sqlalchemy.url', get_engine_url())
target_db = current_app.extensions['migrate'].db

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_metadata():
    if hasattr(target_db, 'metadatas'):
        return target_db.metadatas[None]
    return target_db.metadata


def discard_unknown_revision(connectable):
    """Forget a stamped revision that no longer exists in migrations/versions.

    The migration history was squashed into a single baseline, so a database
    stamped at one of the old revision ids cannot be placed by Alembic any
    more: every command fails with "Can't locate revision identified by
    '<id>'", including `stamp`, which is what would otherwise fix it.

    The schema in such a database is already correct, so the safe move is to
    drop the stale pointer and let the upgrade run: the baseline migration
    detects an existing schema, creates nothing, and leaves the database
    stamped at the current head. Doing it here means a deploy recovers on its
    own instead of needing someone to edit alembic_version by hand.

    Only a revision this project does not know about is removed. A normal,
    resolvable revision is never touched, so this cannot skip real migrations.
    """
    try:
        script = ScriptDirectory.from_config(config)
        known = {rev.revision for rev in script.walk_revisions()}
    except Exception as exc:  # unreadable history: let Alembic report it
        logger.debug('Could not read the migration history: %s', exc)
        return

    if not known:
        return

    with connectable.connect() as connection:
        if not sa.inspect(connection).has_table('alembic_version'):
            return

        stamped = [
            row[0] for row in connection.execute(
                sa.text('SELECT version_num FROM alembic_version')
            )
        ]
        stale = [rev for rev in stamped if rev and rev not in known]
        if not stale:
            return

        logger.warning(
            'Database is stamped at %s, which is not in migrations/versions '
            '(the history was squashed). Clearing the stale record so the '
            'migration can run; the schema itself is left alone.',
            ', '.join(repr(rev) for rev in stale),
        )
        connection.execute(
            sa.text(
                'DELETE FROM alembic_version WHERE version_num IN :stale'
            ).bindparams(sa.bindparam('stale', value=stale, expanding=True))
        )
        connection.commit()


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=get_metadata(), literal_binds=True
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    # this callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # reference: http://alembic.zzzcomputing.com/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    conf_args = current_app.extensions['migrate'].configure_args
    if conf_args.get("process_revision_directives") is None:
        conf_args["process_revision_directives"] = process_revision_directives

    connectable = get_engine()

    discard_unknown_revision(connectable)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            **conf_args
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
