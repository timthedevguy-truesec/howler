from operator import attrgetter

from howler.common.loader import datastore


class DatastoreMixin:
    """Mixin to provide access to the datastore instance."""

    @property
    def ds(self):
        """Return the shared datastore instance.

        Returns:
            The singleton datastore connection used for all persistence operations.
        """
        return datastore()

    def save(self) -> bool:
        """Persist the current model instance to the datastore.

        Determines the target index from the lowercase class name, extracts the
        model's ID from the configured ID field, and saves the instance.

        Returns:
            bool: True if the save operation succeeded, False otherwise.
        """
        index_name = self.__class__.__name__.lower()
        id_field = self.__class__._Model__id_field
        id = attrgetter(id_field)(self)
        return self.ds[index_name].save(id, self)
