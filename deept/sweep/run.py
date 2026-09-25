from enum import Enum


class SweepRun:

    def __init__(self,
        config
    ):
        self.config = config
        self.ident = self.config_as_string()

        self.run_id = None
        self.result = None
        self.__has_result = False
        self.output_folder = None
        self.resume_output_folder = None
    
    def config_as_string(self):
        # Imported here since deept.sweep's __init__ (indirectly) imports this module.
        from deept.sweep import config_to_ident
        return config_to_ident(self.config)

    def has_result(self):
        return self.__has_result
    
    def set_result(self, result):
        self.result = result
        self.__has_result = True

    def get_result(self):
        assert self.has_result()
        return self.result

    def get_result_keys(self):
        keys = []
        for k in self.result.keys():
            keys.append(f'{k}')
            keys.append(f'{k}_std')
        return keys

    def get_result_keys_values(self):
        keys = []
        values = []
        for k, v in self.result.items():
            keys.append(f'{k}')
            keys.append(f'{k}_std')
            values.append(v[0])
            values.append(v[1])
        return keys, values

    def update_config(self, new_config):
        for k, v in new_config.items():
            self.config[k] = v
        self.ident = self.config_as_string()