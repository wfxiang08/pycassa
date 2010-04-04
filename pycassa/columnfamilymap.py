from pycassa.types import Column

__all__ = ['ColumnFamilyMap']

def create_instance(cls, **kwargs):
    instance = cls()
    instance.__dict__.update(kwargs)
    return instance

def combine_columns(column_dict, columns):
    combined_columns = {}
    for column, type in column_dict.iteritems():
        combined_columns[column] = type.default
    for column, value in columns.iteritems():
        col_cls = column_dict.get(column, None)
        if col_cls is not None:
            combined_columns[column] = col_cls.unpack(value)
    return combined_columns

class ColumnFamilyMap(object):
    def __init__(self, cls, column_family, columns=None):
        """
        Construct a ObjectFamily

        Parameters
        ----------
        cls      : class
            Instances of cls are generated on get*() requests
        column_family: ColumnFamily
            The ColumnFamily to tie with cls
        """
        self.cls = cls
        self.column_family = column_family

        self.columns = {}
        for name, column in self.cls.__dict__.iteritems():
            if not isinstance(column, Column):
                continue

            self.columns[name] = column

    def get(self, key, *args, **kwargs):
        """
        Fetch a key from a Cassandra server
        
        Parameters
        ----------
        key : str
            The key to fetch
        super_column : str
            Fetch only this super_column
        read_consistency_level : ConsistencyLevel
            Affects the guaranteed replication factor before returning from
            any read operation

        Returns
        -------
        Class instance
        """
        if 'columns' not in kwargs and not self.column_family.super:
            kwargs['columns'] = self.columns.keys()

        columns = self.column_family.get(key, *args, **kwargs)

        if self.column_family.super:
            if 'super_column' not in kwargs:
                vals = {}
                for super_column, subcols in columns.iteritems():
                    combined = combine_columns(self.columns, subcols)
                    vals[super_column] = create_instance(self.cls, key=key, super_column=super_column, **combined)
                return vals

            combined = combine_columns(self.columns, columns)
            return create_instance(self.cls, key=key, super_column=kwargs['super_column'], **combined)

        combined = combine_columns(self.columns, columns)
        return create_instance(self.cls, key=key, **combined)

    def multiget(self, *args, **kwargs):
        """
        Fetch multiple key from a Cassandra server
        
        Parameters
        ----------
        keys : [str]
            A list of keys to fetch
        super_column : str
            Fetch only this super_column
        read_consistency_level : ConsistencyLevel
            Affects the guaranteed replication factor before returning from
            any read operation

        Returns
        -------
        {'key': Class instance} 
        """
        if 'columns' not in kwargs and not self.column_family.super:
            kwargs['columns'] = self.columns.keys()
        kcmap = self.column_family.multiget(*args, **kwargs)
        ret = {}
        for key, columns in kcmap.iteritems():
            if self.column_family.super:
                if 'super_column' not in kwargs:
                    vals = {}
                    for super_column, subcols in columns.iteritems():
                        combined = combine_columns(self.columns, subcols)
                        vals[super_column] = create_instance(self.cls, key=key, super_column=super_column, **combined)
                    ret[key] = vals
                else:
                    combined = combine_columns(self.columns, columns)
                    ret[key] = create_instance(self.cls, key=key, super_column=kwargs['super_column'], **combined)
            else:
                combined = combine_columns(self.columns, columns)
                ret[key] = create_instance(self.cls, key=key, **combined)
        return ret

    def get_count(self, *args, **kwargs):
        """
        Count the number of columns for a key

        Parameters
        ----------
        key : str
            The key with which to count columns

        Returns
        -------
        int Count of columns
        """
        return self.column_family.get_count(*args, **kwargs)

    def get_range(self, *args, **kwargs):
        """
        Get an iterator over keys in a specified range
        
        Parameters
        ----------
        start : str
            Start from this key (inclusive)
        finish : str
            End at this key (inclusive)
        row_count : int
            Limit the number of rows fetched
        super_column : str
            Fetch only this super_column
        read_consistency_level : ConsistencyLevel
            Affects the guaranteed replication factor before returning from
            any read operation

        Returns
        -------
        iterator over Class instance
        """
        if 'columns' not in kwargs and not self.column_family.super:
            kwargs['columns'] = self.columns.keys()
        for key, columns in self.column_family.get_range(*args, **kwargs):
            if self.column_family.super:
                if 'super_column' not in kwargs:
                    vals = {}
                    for super_column, subcols in columns.iteritems():
                        combined = combine_columns(self.columns, subcols)
                        vals[super_column] = create_instance(self.cls, key=key, super_column=super_column, **combined)
                    yield vals
                else:
                    combined = combine_columns(self.columns, columns)
                    yield create_instance(self.cls, key=key, super_column=kwargs['super_column'], **combined)
            else:
                combined = combine_columns(self.columns, columns)
                yield create_instance(self.cls, key=key, **combined)

    def insert(self, instance, columns=None):
        """
        Insert or update columns for a key

        Parameters
        ----------
        instance : Class instance
            The key to insert or update the columns at
        columns : ['column']
            Limit the columns inserted to this list

        Returns
        -------
        int timestamp
        """
        insert_dict = {}
        if columns is None:
            columns = self.columns.keys()

        for column in columns:
            insert_dict[column] = self.columns[column].pack(instance.__dict__[column])

        if self.column_family.super:
            insert_dict = {instance.super_column: insert_dict}

        return self.column_family.insert(instance.key, insert_dict)

    def remove(self, instance, column=None):
        """
        Remove this instance

        Parameters
        ----------
        instance : Class instance
            Remove the instance where the key is instance.key
        column : str
            If set, remove only this Column. Doesn't do anything for SuperColumns

        Returns
        -------
        int timestamp
        """
        # Hmm, should we only remove the columns specified on construction?
        # It's slower, so we'll leave it out.

        if self.column_family.super:
            return self.column_family.remove(instance.key, column=instance.super_column)
        return self.column_family.remove(instance.key, column)
