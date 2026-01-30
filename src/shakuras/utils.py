from faker.providers import BaseProvider

class CustomWordProvider(BaseProvider):
    def word_with_min_length(self, min_length):
        word = self.generator.word()
        while len(word) < min_length:
            word = self.generator.word()
        return word
